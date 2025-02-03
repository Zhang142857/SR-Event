from flask import Flask, render_template, request, jsonify, send_file
import requests
import uuid
import json
import socket
import threading
import time
from datetime import datetime
import os
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

app = Flask(__name__)

# 全局变量
class GlobalState:
    def __init__(self):
        self.device_id = str(uuid.uuid4())
        self.device_name = None
        self.server_ip = None
        self.server_port = None
        self.is_registered = False
        self.transfer_tasks = {}

state = GlobalState()

class ServiceDiscoveryListener(ServiceListener):
    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            state.server_ip = socket.inet_ntoa(info.addresses[0])
            state.server_port = info.port
            print(f"Found server at {state.server_ip}:{state.server_port}")

    def remove_service(self, zc, type_, name):
        pass

    def update_service(self, zc, type_, name):
        pass

def start_service_discovery():
    print("Starting service discovery...")
    zeroconf = Zeroconf()
    listener = ServiceDiscoveryListener()
    browser = ServiceBrowser(zeroconf, "_erevent._tcp.local.", listener)
    return zeroconf

def heartbeat_thread():
    while True:
        if state.is_registered and state.server_ip:
            try:
                requests.post(
                    f"http://{state.server_ip}:{state.server_port}/api/heartbeat",
                    json={'device_id': state.device_id}
                )
            except:
                print("Heartbeat failed")
        time.sleep(30)

@app.route('/')
def index():
    if not state.is_registered:
        return render_template('client_register.html')
    return render_template('client_main.html', 
                         device_name=state.device_name,
                         device_id=state.device_id)

@app.route('/api/register', methods=['POST'])
def register_device():
    print("Received registration request")
    if not state.server_ip:
        print("No server found yet")
        return jsonify({
            'status': 'error',
            'message': '正在搜索服务器，请稍后再试'
        }), 400

    try:
        state.device_name = request.json.get('device_name')
        print(f"Attempting to register device: {state.device_name} to server: {state.server_ip}:{state.server_port}")
        
        response = requests.post(
            f"http://{state.server_ip}:{state.server_port}/api/register",
            json={
                'device_id': state.device_id,
                'device_name': state.device_name
            },
            timeout=5  # 添加超时设置
        )
        print(f"Server response status: {response.status_code}")
        print(f"Server response: {response.text}")
        
        if response.status_code == 200:
            state.is_registered = True
            return jsonify({'status': 'success'})
        return jsonify({
            'status': 'error',
            'message': f'注册失败: {response.text}'
        }), 400
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': '无法连接到服务器，请确保服务器正在运行'
        }), 500
    except Exception as e:
        print(f"Unexpected error during registration: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'注册过程中出现错误: {str(e)}'
        }), 500

@app.route('/api/devices')
def get_devices():
    if not state.server_ip:
        return jsonify({'devices': []})
    
    try:
        response = requests.get(
            f"http://{state.server_ip}:{state.server_port}/api/devices"
        )
        if response.status_code == 200:
            devices = response.json()['devices']
            # 移除自己
            if state.device_id in devices:
                del devices[state.device_id]
            return jsonify({'devices': devices})
    except:
        pass
    return jsonify({'devices': []})

@app.route('/api/transfer/send', methods=['POST'])
def send_file():
    if 'file' not in request.files:
        return jsonify({
            'status': 'error',
            'message': '没有文件被上传'
        }), 400

    target_device = request.form.get('target_device')
    if not target_device:
        return jsonify({
            'status': 'error',
            'message': '未指定目标设备'
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            'status': 'error',
            'message': '没有选择文件'
        }), 400

    # 保存文件到临时目录
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    file.save(temp_path)

    # 创建接收服务器
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 0))
    server_socket.listen(1)
    _, port = server_socket.getsockname()

    # 发送传输请求到服务器
    try:
        response = requests.post(
            f"http://{state.server_ip}:{state.server_port}/api/transfer/init",
            json={
                'from_device': state.device_id,
                'to_device': target_device,
                'file_info': {
                    'filename': file.filename,
                    'size': os.path.getsize(temp_path),
                    'receive_port': port
                }
            }
        )
        
        if response.status_code == 200:
            transfer_id = response.json()['transfer_id']
            
            # 启动传输线程
            def transfer_thread():
                try:
                    conn, addr = server_socket.accept()
                    with open(temp_path, 'rb') as f:
                        while chunk := f.read(8192):
                            conn.send(chunk)
                    conn.close()
                finally:
                    server_socket.close()
                    os.remove(temp_path)

            threading.Thread(target=transfer_thread, daemon=True).start()
            
            return jsonify({
                'status': 'success',
                'transfer_id': transfer_id
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/transfer/receive', methods=['POST'])
def receive_file():
    data = request.json
    file_info = data.get('file_info')
    source_ip = data.get('source_ip')
    receive_port = file_info.get('receive_port')

    downloads_dir = os.path.expanduser('~/Downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    
    def receive_thread():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((source_ip, receive_port))
            
            filepath = os.path.join(downloads_dir, file_info['filename'])
            with open(filepath, 'wb') as f:
                while chunk := s.recv(8192):
                    f.write(chunk)
            s.close()
        except Exception as e:
            print(f"接收文件失败: {e}")

    threading.Thread(target=receive_thread, daemon=True).start()
    return jsonify({'status': 'success'})

def main():
    # 创建必要的目录
    os.makedirs('temp', exist_ok=True)
    
    print("Starting ER-Event client...")
    # 启动服务发现
    zeroconf = start_service_discovery()
    
    # 启动心跳线程
    threading.Thread(target=heartbeat_thread, daemon=True).start()
    
    try:
        # 启动Flask应用
        # 使用随机端口，这样同一台机器可以运行多个客户端
        port = 0
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', port))
        port = sock.getsockname()[1]
        sock.close()
        
        print(f"Client web interface available at http://localhost:{port}")
        app.run(host='localhost', port=port, debug=True)
    finally:
        zeroconf.close()

if __name__ == '__main__':
    main()
