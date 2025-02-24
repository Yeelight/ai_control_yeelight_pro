from flask_socketio import SocketIO
from datetime import datetime  # Import datetime module

class Logger:
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio

    def log_message(self, message: str, level: str = "INFO"):
        """Log formatted messages and emit to WebSocket."""
        log_entry = f"[{level}] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message} \n"
        print(log_entry)  # Print to console
        if self.socketio:
            self.socketio.emit('log_update', {'message': log_entry})  # Emit log message to WebSocket clients
            self.socketio.sleep(0.05)  # 确保事件循环继续执行

    def log_message_stream(self, message: str):
        """Log formatted messages and emit to WebSocket."""
        try:
            print(message, end='', flush=True)  # 实时输出
            if self.socketio:
                self.socketio.emit('log_update', {'message': message}, namespace='/')  # 实时发送到客户端
                self.socketio.sleep(0.05)  # 确保事件循环继续执行
        except Exception as e:
            print(f"日志输出失败: {str(e)}", flush=True)  # 打印错误信息
        
1
# 全局 logger 实例
logger = None

def init_logger(socketio: SocketIO):
    """初始化全局 logger 实例"""
    global logger
    logger = Logger(socketio)

def get_logger() -> Logger:
    """获取全局 logger 实例"""
    if logger is None:
        raise Exception("Logger has not been initialized. Call init_logger first.")
    return logger 