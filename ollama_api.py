from langchain_community.llms import Ollama
from ollama import Client
from typing import List, Dict


def log_message(message: str, level: str = "INFO"):
    """打印格式化的日志信息并推送到 WebSocket"""
    log_entry = f"***** [{level}] {message} *****"
    print(log_entry)  # Print to console

def get_available_models() -> List[Dict]:
    """
    获取当前系统中可用的 Ollama 模型列表
    
    Returns:
        模型列表，每个模型包含名称和其他信息
    """
    try:
        client = Client(host='http://localhost:11434')
        response = client.list()
        log_message("获取可用模型列表")
        return response['models']
    except Exception as e:
        log_message(f"获取模型列表时发生错误: {str(e)}", level="ERROR")
        return []
    
def initialize_llm():
    """
    初始化 LLM 模型，使用本机第一个可用的模型
    """
    try:
        available_models = get_available_models()  # 使用 Langchain 获取模型列表
        
        if not available_models:  # 检查是否有可用模型
            log_message("未找到任何可用的模型！", level="ERROR")
            log_message("请使用以下命令安装模型：")
            log_message("ollama pull llama2")
            return None  # 没有可用模型时返回 None
        
        # 直接使用第一个可用的模型的名称
        selected_model = available_models[0]['model']  # 确保提取模型名称
        log_message(f"使用的 ollama 本地模型为: {selected_model}")
        return Ollama(model=selected_model, temperature=0)  # 传递模型名称字符串
    except Exception as e:
        log_message(f"获取模型列表失败: {str(e)}", level="ERROR")
        return None
    