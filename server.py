from flask import Flask, request, jsonify
from zeroconf import ServiceInfo, Zeroconf
import socket
import json
import threading
import time
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# 存储设备信息
devices = {}
# 存储传输任务
transfer_tasks = {}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

# 注册Zeroconf服务
def register_zeroconf_service():
    local_ip = get_local_ip()
    logging.info(f"Local IP: {local_ip}")
    zeroconf = Zeroconf()
    service_info = ServiceInfo(
        "_erevent._tcp.local.",
        "ER-Event Server._erevent._tcp.local.",
        addresses=[socket.inet_aton(local_ip)],
        port=5000,
        properties={},
    )
    zeroconf.register_service(service_info)
    logging.info("Zeroconf service registered")
    return zeroconf

@app.route('/api/register', methods=['POST'])
def register_device():
    logging.info("Received registration request")
    try:
        data = request.json
        logging.info(f"Registration data: {data}")
        
        device_id = data.get('device_id')
        device_name = data.get('device_name')
        device_ip = request.remote_addr
        
        if not device_id or not device_name:
            logging.error("Missing device_id or device_name")
            return jsonify({
                'status': 'error',
                'message': '缺少设备ID或设备名称'
            }), 400
        
        devices[device_id] = {
            'name': device_name,
            'ip': device_ip,
            'last_seen': datetime.now().isoformat(),
            'status': 'online'
        }
        
        logging.info(f"Device registered successfully: {device_id} - {device_name}")
        return jsonify({
            'status': 'success',
            'message': 'Device registered successfully'
        })
    except Exception as e:
        logging.error(f"Error during registration: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'注册失败: {str(e)}'
        }), 500

@app.route('/api/devices', methods=['GET'])
def get_devices():
    logging.info("Received devices list request")
    # 清理超时设备
    current_time = datetime.now()
    for device_id in list(devices.keys()):
        last_seen = datetime.fromisoformat(devices[device_id]['last_seen'])
        if (current_time - last_seen).seconds > 60:  # 60秒超时
            devices[device_id]['status'] = 'offline'
    
    return jsonify({
        'status': 'success',
        'devices': devices
    })

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    try:
        data = request.json
        device_id = data.get('device_id')
        if device_id in devices:
            devices[device_id]['last_seen'] = datetime.now().isoformat()
            devices[device_id]['status'] = 'online'
        return jsonify({'status': 'success'})
    except Exception as e:
        logging.error(f"Error during heartbeat: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/transfer/init', methods=['POST'])
def init_transfer():
    try:
        data = request.json
        from_device = data.get('from_device')
        to_device = data.get('to_device')
        file_info = data.get('file_info')
        
        transfer_id = f"{from_device}-{to_device}-{int(time.time())}"
        transfer_tasks[transfer_id] = {
            'from_device': from_device,
            'to_device': to_device,
            'file_info': file_info,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        logging.info(f"Transfer initialized: {transfer_id}")
        return jsonify({
            'status': 'success',
            'transfer_id': transfer_id
        })
    except Exception as e:
        logging.error(f"Error initializing transfer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/transfer/status/<transfer_id>', methods=['GET'])
def get_transfer_status(transfer_id):
    if transfer_id in transfer_tasks:
        return jsonify({
            'status': 'success',
            'task': transfer_tasks[transfer_id]
        })
    return jsonify({
        'status': 'error',
        'message': 'Transfer not found'
    }), 404

def main():
    logging.info("Starting ER-Event server...")
    # 注册Zeroconf服务
    zeroconf = register_zeroconf_service()
    local_ip = get_local_ip()
    logging.info(f"Server running on {local_ip}:5000")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        logging.info("Shutting down server...")
        zeroconf.unregister_all_services()
        zeroconf.close()

if __name__ == '__main__':
    main()
