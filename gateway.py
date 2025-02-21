import socket
import json
import time
import atexit  # 导入 atexit 模块
from logger import Logger  # 导入 Logger 类
import eventlet.queue as queue  # 使用 eventlet 的队列
from match_name import NameMatcher

# 全局变量
tcp_sock = None  # 用于存储 TCP socket

def close_socket():
    """关闭 TCP socket 的函数"""
    global tcp_sock
    if tcp_sock:
        tcp_sock.close()
        print("TCP socket 已关闭")

# 注册关闭函数
atexit.register(close_socket)

def discover_gateway(websocket, scan_only=False):
    """
    通过 UDP 广播发现网关
    返回: (网关信息字典)
    """
    logger = Logger(websocket)  # 使用 websocket
    logger.log_message("开始扫描发现附近网关")

    # 创建 UDP socket
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_sock.settimeout(5)  # 设置超时时间
    
    try:
        # 发送广播消息
        broadcast_addr = '<broadcast>'  # 或使用具体的广播地址如 "192.168.1.255"
        logger.log_message(f"发送广播消息到地址: {broadcast_addr}")
        udp_sock.sendto(b"YEELIGHT_GATEWAY_CONTROL_DISCOVER", (broadcast_addr, 1982))
        
        # 接收响应
        logger.log_message("等待网关响应...")
        data, addr = udp_sock.recvfrom(1024)
        response = data.decode()
        logger.log_message(f"收到来自 {addr} 的响应: {response}")
        
        # 解析响应，处理可能的格式问题
        gateway_info = {}
        for line in response.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)  # 最多分割一次
                gateway_info[key.strip()] = value.strip()
        
        if 'ip' not in gateway_info:
            raise Exception("网关响应中未包含 IP 地址")
        
        logger.log_message(f"解析到的网关信息：{gateway_info}")
        if scan_only:
            return [gateway_info]  # 返回列表以保持一致性
        else:
            # 创建 TCP 连接
            global tcp_sock  # 声明为全局变量
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.settimeout(8)  # 设置超时时间为 8 秒
            tcp_sock.connect((gateway_info['ip'], 65443))
            logger.log_message(f"成功连接到网关: {gateway_info['ip']}:65443")
            
            # 返回套接字和已连接的网关
            return tcp_sock, gateway_info['ip']
        
    except Exception as e:
        logger.log_message(f"发现网关失败: {str(e)}", level="ERROR")
        raise
    finally:
        udp_sock.close() 
        logger.log_message("UDP socket 已关闭")

def connect_to_gateway(gateway_info, websocket):
    """
    连接到指定的网关
    返回: (socket对象, 网关地址)
    """
    logger = Logger(websocket)  # 使用 websocket
    gateway_ip = gateway_info['ip']
    logger.log_message(f"尝试连接到网关: {gateway_ip}")

    # 创建 TCP 连接
    global tcp_sock  # 声明为全局变量
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.settimeout(8)  # 设置超时时间为 8 秒
    tcp_sock.connect((gateway_ip, 65443))
    
    logger.log_message(f"成功连接到网关: {gateway_ip}:65443")
    return gateway_ip


def send_command(websocket, command):
    """发送 JSON 命令并接收响应"""
    logger = Logger(websocket)  # 使用 websocket
    payload = json.dumps(command)
    logger.log_message(f"发送命令: {payload}")
    tcp_sock.sendall((payload + "\r\n").encode())
   
    # 接收响应
    buffer = bytearray()
    tcp_sock.settimeout(2)  # 设置每次recv的超时时间
    end_time = time.time() + 5  # 总超时5秒
    
    try:
        while time.time() < end_time:
            try:
                chunk = tcp_sock.recv(4096)
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
        logger.log_message(f"接收到的响应: {decoded_data}")
        
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
                
        # 校验返回的 JSON 对象的 id 和 method
        for obj in json_objects:
            method = obj.get("method", "")
            command_method = command["method"]

            if method == "gateway_post.prop":
                logger.log_message("收到 gateway_post.prop，重新发送命令")
                return send_command(websocket, command)  # 重新发送命令

            if command_method=="gateway_get.topology" and method.endswith("topology"):
                return obj

            if command_method =="gateway_get.room" and obj.get("rooms") == None:
                logger.log_message(f"命令方法不匹配: {command_method} != {method}", level="ERROR")
                return send_command(websocket, command)  # 重新发送命令

            if command_method =="gateway_get.topology" and method!="gateway_post.topology":
                logger.log_message(f"命令方法不匹配: {command_method} != {method}", level="ERROR")
                return send_command(websocket, command)  # 重新发送命令

            if obj.get("id") == command["id"]:
                return obj
        
        raise ValueError("未找到匹配的响应")
        
    except json.JSONDecodeError as e:
        logger.log_message(f"JSON解析失败（位置 {e.pos}）: {str(e)}", level="ERROR")
        print(f"[DEBUG] 原始响应数据: {decoded_data[:2000]}...")  # 截断长数据
        raise ValueError(f"JSON解析失败（位置 {e.pos}）: {str(e)}")
    

def get_topology(websocket):
    """
    获取设备拓扑信息
    """
    logger = Logger(websocket)  # 使用 websocket

    request = {
        "id": int(time.time()),
        "method": "gateway_get.topology",
    }
    
    # 发送请求
    logger.log_message("请求设备拓扑信息")
    response = send_command(websocket, request)  # 确保不传递 websocket 参数
    nodes = response.get("nodes", [])
    logger.log_message(f"接收到的拓扑信息: {nodes}")

    # nt 类型映射
    nt_type_mapping = {
        1: "房间",
        2: "Mesh子设备",
        3: "自定义分组",
        4: "Mesh组",
        5: "房屋/整屋",
        6: "情景"
    }
    
    # 封装节点信息
    wrapped_nodes = []
    for node in nodes:
        nt_type = node.get("nt")
        wrapped_node = {
            "type": nt_type,  # 节点类型
            "type_description": nt_type_mapping.get(nt_type, "未知类型"),  # 类型描述
            "id": node.get("id"),     # 节点 ID
            "name": node.get("n"),    # 节点名称
            "device_type": node.get("type")  # 设备类型
        }
        
        wrapped_nodes.append(wrapped_node)



    room_request = {
        "id": int(time.time()),
        "method": "gateway_get.room",
        "params": {"id": 0}
    }
    logger.log_message(f"请求房间信息: {room_request}")
    room_response = send_command(websocket, room_request)
    rooms = room_response.get("rooms", [])
    logger.log_message(f"接收到的房间信息: {rooms}")
    
    # 将每个房间对象添加到 wrapped_nodes
    for room in rooms:
        room_node = {
            "type": 1,
            "type_description": "房间",
            "id": room.get("id"),
            "name": room.get("n"),
            "device_type": "房间"
        }
        wrapped_nodes.append(room_node)

    return wrapped_nodes

def discover_and_connect_gateway(websocket, scan_only=False):
    """
    扫描并连接到网关
    如果 scan_only 为 True，则仅返回扫描到的网关信息
    """
    logger = Logger(websocket)  # 使用 websocket
    try:
        # 扫描网关
        logger.log_message("开始扫描并连接到网关")
        gateways = discover_gateway(websocket, scan_only=True)
        
        if scan_only:
            logger.log_message("仅扫描网关信息")
            return gateways  # 返回列表以保持一致性

        # 尝试连接到每个网关
        for gateway in gateways:
            try:
                tcp_sock, gateway_ip = connect_to_gateway(gateway, websocket)
                logger.log_message(f"成功连接到网关: {gateway_ip}")
                return tcp_sock, gateway_ip
            except ConnectionRefusedError:
                logger.log_message(f"连接到网关 {gateway['ip']} 被拒绝，尝试下一个网关", level="ERROR")
                continue  # 尝试下一个网关

        raise Exception("所有网关连接均被拒绝")
        
    except Exception as e:
        logger.log_message(f"扫描或连接网关时出错: {str(e)}", level="ERROR")
        raise

def control_device(command_data, websocket):
    """
    控制设备
    command_data: 包含控制命令的字典
    """
    global tcp_sock
    logger = Logger(websocket)  # 使用 websocket

    try:
        if tcp_sock is None:
            logger.log_message("Socket 未连接，无法发送命令", level="ERROR")
            return "Socket 未连接，无法发送命令"

        # 获取拓扑信息
        logger.log_message("获取拓扑信息")
        nodes = get_topology(websocket)
        
        # 获取命令信息
        name = command_data.get('name')
        action = command_data.get('action')
        domain = command_data.get('domain')
        location = command_data.get('location')
        parameters = command_data.get('parameters')
        
        # 根据 domain 和 nt 类型过滤设备
        domain_filters = {
            "light": lambda d: d.get("type") in [1, 2, 3, 4] and d.get("nt") in [2, 3, 4],
            "scene": lambda d: d.get("nt") == 6,
            "room": lambda d: d.get("nt") == 1 if location == "all" else d.get("nt") == 5,
            "switch": lambda d: d.get("type") in [7, 13, 128]
        }

        if domain in domain_filters:
            logger.log_message(f"查找网关下是否有 name 为: {name} 的{domain}")
            domain_nodes = [d for d in nodes if domain_filters[domain](d)]
            filtered_nodes = NameMatcher.find_devices_by_name(domain_nodes, name)
            
            if not filtered_nodes:
                logger.log_message(f"未找到符合条件的节点信息: {name}", level="ERROR")
                return f"未找到符合条件的节点信息: {name}"
        else:
            logger.log_message(f"未知的 domain 类型: {domain}", level="ERROR")
            return f"未知的 domain 类型: {domain}"
        
        # 构建控制指令
        logger.log_message("构建控制指令")
        nodes = []
        scenes = []
        command = {
            "id": int(time.time()),
            "method": "gateway_set.prop",
            "nodes": nodes,
            "scenes": scenes
        }
        
        for node in filtered_nodes:
            nt_type = node.get("nt")

            if nt_type == 6:
                scene_command = {
                    "id": node["id"],
                }
                scenes.append(scene_command)
            else:
                node_command = {
                    "id": node["id"],
                    "nt": nt_type,
                    "set": {}
                }
                if action == "turn_on":
                    node_command["set"]["p"] = True
                elif action == "turn_off":
                    node_command["set"]["p"] = False
                nodes.append(node_command)
            

        logger.log_message(f"构建命令为: {command}")
        
        # 发送控制命令  
        logger.log_message("发送控制命令")
        send_command(websocket, command)  # 确保传递 command 参数
        
        logger.log_message("命令已成功发送")
        return "命令已成功发送"
        
    except Exception as e:
        error_message = f"控制设备时出错: {str(e)}"
        logger.log_message(error_message, level="ERROR")
        return error_message


