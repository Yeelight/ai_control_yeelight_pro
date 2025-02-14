import os

# 使用os.getenv获取环境变量，确保Docker传递的变量优先
os.environ['WHISPER_MODEL_SIZE'] = os.getenv('WHISPER_MODEL_SIZE', 'base')  # 默认值为 'base'
os.environ['OLLAMA_MODEL_NAME'] = os.getenv('OLLAMA_MODEL_NAME', 'deepseek-r1:7b')  # 默认值
os.environ['OLLAMA_IP_PORT'] = os.getenv('OLLAMA_IP_PORT', 'http://192.168.0.254:11434')  # 默认值 