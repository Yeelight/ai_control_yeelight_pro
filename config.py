import os

# Set the Whisper model size
os.environ['WHISPER_MODEL_SIZE'] = 'small'  # 可以根据需要更改为  'base', 'small', 'medium', 'large' 等 
os.environ['OLLAMA_MODEL_NAME'] = 'deepseek-r1:1.5b'  # 可以根据需要更改为  'base', 'small', 'medium', 'large' 等 