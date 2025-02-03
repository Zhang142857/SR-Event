from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.list import MDList, TwoLineIconListItem, IconLeftWidget
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform
from kivy.lang import Builder
import requests
import threading
import uuid
import json
import socket
import time
from datetime import datetime
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
import os
from functools import partial

# 设置窗口大小（仅用于测试）
if platform != 'android':
    Window.size = (400, 600)

# KV语言字符串
KV = '''
ScreenManager:
    RegisterScreen:
    MainScreen:

<RegisterScreen>:
    name: 'register'
    MDBoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(20)

        MDLabel:
            text: 'ER-Event 客户端'
            halign: 'center'
            font_style: 'H5'
            size_hint_y: None
            height: dp(50)

        MDCard:
            orientation: 'vertical'
            padding: dp(20)
            spacing: dp(10)
            size_hint: None, None
            size: "280dp", "180dp"
            pos_hint: {"center_x": .5, "center_y": .5}

            MDLabel:
                id: server_status
                text: '正在搜索服务器...'
                halign: 'center'
                theme_text_color: "Secondary"

            MDTextField:
                id: device_name
                hint_text: "输入设备名称"
                helper_text_mode: "on_error"

            MDRaisedButton:
                id: register_button
                text: "注册设备"
                pos_hint: {"center_x": .5}
                on_release: root.register_device()
                disabled: True

<MainScreen>:
    name: 'main'
    MDBoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(10)

        MDTopAppBar:
            title: "ER-Event"
            right_action_items: [["refresh", lambda x: root.refresh_devices()]]

        MDScrollView:
            MDList:
                id: device_list

        MDLabel:
            id: status_label
            text: ""
            halign: 'center'
            size_hint_y: None
            height: dp(30)
'''

class RegisterScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()

    def on_enter(self):
        Clock.schedule_interval(self.check_server, 2)

    def check_server(self, dt):
        if self.app.server_ip:
            self.ids.server_status.text = f'已连接到服务器: {self.app.server_ip}'
            self.ids.register_button.disabled = False
            return False
        return True

    def register_device(self):
        device_name = self.ids.device_name.text
        if not device_name:
            self.ids.device_name.error = True
            self.ids.device_name.helper_text = "请输入设备名称"
            return

        try:
            response = requests.post(
                f"http://{self.app.server_ip}:{self.app.server_port}/api/register",
                json={
                    'device_id': self.app.device_id,
                    'device_name': device_name
                }
            )
            if response.status_code == 200:
                self.app.device_name = device_name
                self.app.is_registered = True
                self.manager.current = 'main'
            else:
                self.ids.server_status.text = "注册失败：" + response.json().get('message', '')
        except Exception as e:
            self.ids.server_status.text = f"注册失败：{str(e)}"

class MainScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        Clock.schedule_interval(self.refresh_devices, 5)

    def refresh_devices(self, *args):
        if not self.app.is_registered:
            return
        
        try:
            response = requests.get(
                f"http://{self.app.server_ip}:{self.app.server_port}/api/devices"
            )
            if response.status_code == 200:
                devices = response.json()['devices']
                self.update_device_list(devices)
        except Exception as e:
            self.ids.status_label.text = f"刷新设备列表失败：{str(e)}"

    def update_device_list(self, devices):
        self.ids.device_list.clear_widgets()
        for device_id, device_info in devices.items():
            if device_id != self.app.device_id and device_info['status'] == 'online':
                item = TwoLineIconListItem(
                    text=device_info['name'],
                    secondary_text="在线",
                    on_release=partial(self.select_file, device_id)
                )
                icon = IconLeftWidget(icon="laptop")
                item.add_widget(icon)
                self.ids.device_list.add_widget(item)

    def select_file(self, target_device, *args):
        # TODO: 实现文件选择和发送功能
        pass

class ServiceDiscoveryListener(ServiceListener):
    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            app = MDApp.get_running_app()
            app.server_ip = socket.inet_ntoa(info.addresses[0])
            app.server_port = info.port

    def remove_service(self, zc, type_, name):
        pass

    def update_service(self, zc, type_, name):
        pass

class EREventApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.device_id = str(uuid.uuid4())
        self.device_name = None
        self.server_ip = None
        self.server_port = None
        self.is_registered = False
        self.zeroconf = None

    def build(self):
        self.theme_cls.primary_palette = "Blue"
        return Builder.load_string(KV)

    def on_start(self):
        # 启动服务发现
        self.zeroconf = Zeroconf()
        self.listener = ServiceDiscoveryListener()
        self.browser = ServiceBrowser(
            self.zeroconf, "_erevent._tcp.local.", self.listener
        )

        # 启动心跳线程
        threading.Thread(target=self.heartbeat_thread, daemon=True).start()

    def heartbeat_thread(self):
        while True:
            if self.is_registered and self.server_ip:
                try:
                    requests.post(
                        f"http://{self.server_ip}:{self.server_port}/api/heartbeat",
                        json={'device_id': self.device_id}
                    )
                except:
                    pass
            time.sleep(30)

    def on_stop(self):
        if self.zeroconf:
            self.zeroconf.close()

if __name__ == '__main__':
    EREventApp().run()
