import socket
import json
import time
from logger import Logger  # 导入 Logger 类

def discover_and_connect_gateway(socketio):
    """
    通过 UDP 广播发现并连接到网关
    返回: (socket对象, 网关地址)
    """
    logger = Logger(socketio)  # 初始化 Logger
    logger.log_message("扫描发现附近网关")

    # 创建 UDP socket
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_sock.settimeout(5)  # 设置超时时间
    
    try:
        # 发送广播消息
        broadcast_addr = '<broadcast>'  # 或使用具体的广播地址如 "192.168.1.255"
        udp_sock.sendto(b"YEELIGHT_GATEWAY_CONTROL_DISCOVER", (broadcast_addr, 1982))
        
        # 接收响应
        data, addr = udp_sock.recvfrom(1024)
        response = data.decode()
        
        # 解析响应，处理可能的格式问题
        gateway_info = {}
        for line in response.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)  # 最多分割一次
                gateway_info[key.strip()] = value.strip()
        
        if 'ip' not in gateway_info:
            raise Exception("网关响应中未包含 IP 地址")
        
        logger.log_message(f"扫描到网关信息：{gateway_info}")

        gateway_ip = gateway_info['ip']

        # 创建 TCP 连接
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.connect((gateway_ip, 65443))
        
        logger.log_message(f"成功连接到网关: {gateway_ip}:65443")
        return tcp_sock, gateway_ip
        
    except Exception as e:
        logger.log_message(f"连接网关失败: {str(e)}", level="ERROR")
        raise
    finally:
        udp_sock.close() 



def send_command(sock, command):
    """发送 JSON 命令并接收响应"""
    payload = json.dumps(command)
    sock.sendall((payload + "\r\n").encode())
   
    # 接收响应
    buffer = bytearray()
    sock.settimeout(2)  # 设置每次recv的超时时间
    end_time = time.time() + 5  # 总超时5秒
    
    try:
        while time.time() < end_time:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                # 检查结束标记（字节级别检查）
                if buffer.endswith(b'\r\n'):
                    break
            except socket.timeout:
                continue  # 继续检查总超时
            
        if not buffer.endswith(b'\r\n'):
            raise TimeoutError("接收响应超时")
            
        # 解码并解析
        decoded_data = buffer[:-2].decode('utf-8', errors='replace')
        
        # 处理多个JSON对象情况
        json_objects = []
        decoder = json.JSONDecoder()
        offset = 0
        
        while offset < len(decoded_data):
            try:
                obj, idx = decoder.raw_decode(decoded_data[offset:])
                json_objects.append(obj)
                offset += idx
            except json.JSONDecodeError:
                break  # 忽略无效尾部数据
                
        if not json_objects:
            raise ValueError("响应中未找到有效JSON数据")
            
        return json_objects[-1]
        
    except json.JSONDecodeError as e:
        print(f"[DEBUG] 原始响应数据: {decoded_data[:2000]}...")  # 截断长数据
        raise ValueError(f"JSON解析失败（位置 {e.pos}）: {str(e)}")

def get_topology(sock):
    """
    获取设备拓扑信息
    """
    request = {
        "id": int(time.time()),
        "method": "gateway_get.topology",
    }
    
    # 发送请求
    response = send_command(sock, request)
    return response.get("nodes", [])

