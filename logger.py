from flask_socketio import SocketIO
from datetime import datetime  # Import datetime module

class Logger:
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio

    def log_message(self, message: str, level: str = "INFO"):
        """Log formatted messages and emit to WebSocket."""
        log_entry = f"[{level}] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message} \n"
        print(log_entry)  # Print to console
        self.socketio.emit('log_update', {'message': log_entry})  # Emit log message to WebSocket clients

    def log_message_stream(self, message: str):
        """Log formatted messages and emit to WebSocket."""
        self.socketio.emit('log_update', {'message': message})  # Emit log message to WebSocket clients

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