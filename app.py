from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS  # Import CORS
from flask_socketio import SocketIO, emit  # Import SocketIO
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from typing import List, Dict
import whisper
import opencc
import os
import subprocess  # 导入 subprocess 模块以调用 shell 命令
import time
import warnings
import soundfile as sf  # For reading and writing audio files
from pydub import AudioSegment
from ollama_api import initialize_llm
from utils import extract_json
from gateway import get_topology,send_command,discover_gateway,connect_to_gateway
from pydantic import BaseModel, model_validator
from logger import init_logger, get_logger  # 在需要时获取 Logger 实例  # 导入初始化函数
from prompts import prompt  # Import the prompt variable from prompts.py
from datetime import datetime
from config import *  # 导入配置文件中的环境变量
from piper import PiperVoice
import uuid
import wave

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.secret_key = 'your_secret_key'  # 设置一个密钥用于会话
socketio = SocketIO(app, cors_allowed_origins="*")  # 允许所有来源

# 定义模型和配置文件的路径
model_path = "tts/zh_CN-huayan-medium.onnx"
config_path = "tts/zh_CN-huayan-medium.onnx.json"

# 检查文件是否存在
if not os.path.exists(model_path) or not os.path.exists(config_path):
    raise FileNotFoundError("模型或配置文件未找到，请确保它们已下载并存储在 tts 目录中。")

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module='whisper')

# Load the Whisper model based on the environment variable
model_size = os.getenv('WHISPER_MODEL_SIZE', 'base')  # 默认模型大小为 'base'
model = whisper.load_model(model_size)  # 加载指定大小的模型

# 初始化 Ollama 的模型
llm = initialize_llm()

if llm is None:
    raise RuntimeError("未能初始化 Ollama 模型，请确保有可用模型。")

# Define the prompt variable before using it
# prompt is now imported from prompts.py
prompt_template = PromptTemplate(
    template=prompt,
    input_variables=["user_input"]
)

# 创建处理链
chain = (
    {"user_input": RunnablePassthrough()} 
    | prompt_template 
    | llm 
    | StrOutputParser()
)

# Global variables to hold the socket and gateway address
sock = None
gateway_address = None

# 初始化 Logger
init_logger(socketio)

logger = get_logger()  # 在需要时获取 Logger 实例

# Function to log messages
def log_message(level, message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"***** [{level}] [{timestamp}] {message} *****\n"
    # Add your logging logic here

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    logger.log_message("Audio file processing.")  # Log success message
    logger.log_message("Processing with the Whisper local model.")  # Log success message

    audio_path = None  # Initialize audio_path
    wav_path = None    # Initialize wav_path
    try:
        # 处理音频文件
        audio_file = request.files['audio']
        audio_path = os.path.join('uploads', audio_file.filename)
        audio_file.save(audio_path)

        # Convert to WAV format if necessary and ensure mono and 16kHz sample rate
        audio_segment = AudioSegment.from_file(audio_path)  # Read the webm file

        # Convert to mono and 16kHz sample rate
        audio_segment = audio_segment.set_channels(1).set_frame_rate(16000)

        # Export as WAV
        wav_path = audio_path.replace('.webm', '.wav')
        audio_segment.export(wav_path, format='wav')

        # Read the WAV file
        audio, sample_rate = sf.read(wav_path)

        # Ensure audio is in float32 format
        if audio.dtype != 'float32':
            audio = audio.astype('float32')

        logger.log_message("Audio file processed successfully.")  # Log success message
    except Exception as e:
        logger.log_message(f"Error processing audio file: {str(e)}", level="ERROR")
        return jsonify({'status': 'error', 'message': 'Audio processing failed.'}), 500
    finally:
        # Clean up the uploaded and converted files
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)  # Clean up the uploaded file
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)  # Clean up the converted WAV file
    logger.log_message("Processing with the Whisper local model.")  # Log success message

    # 转录音频为文本（繁体字输出）
    result = model.transcribe(audio, language="zh")

    # 输出转录文本（可能是繁体字）
    log_message("Original Transcription (Traditional):", result['text'])

    # 使用 OpenCC 将繁体字转换为简体字
    converter = opencc.OpenCC('t2s')  # t2s.json: 繁体转简体的配置文件
    simplified_text = converter.convert(result['text'])

    return jsonify({'text': simplified_text})

@app.route('/submit', methods=['POST'])
def submit():
    user_input = request.json.get('user_input')  # 获取用户输入
    try:
        logger.log_message("使用的 ollama 本地模型为:" + llm.base_url + "/" +llm.model)
        
        # 获取模型输出（流式处理）
        logger.log_message("ollama 模型响应开始")
        full_response = []
        for chunk in chain.stream(user_input):
            logger.log_message_stream(chunk)
            full_response.append(chunk)
        logger.log_message_stream("\n")
        print("\n***** ollama 模型响应结束 *****")
        
        # 合并响应内容
        response = ''.join(full_response)
        
        # 解析响应为 JSON
        try:
            command_data = extract_json(response)
            result_message = control_device(command_data) if command_data else "无效的命令数据"
            
            # 使用 Piper 进行语音合成，将结果信息转换为音频文件
            voice = PiperVoice.load(model_path, config_path=config_path)
            unique_filename = f'static/result_audio_{uuid.uuid4()}.wav'  # 生成唯一文件名
            
            # 合成语音并写入 WAV 文件
            try:
                # 调用 synthesize 方法生成音频数据
                with wave.open(unique_filename, 'wb') as wav_file:  # 打开 WAV 文件以写入
                    voice.synthesize(result_message, wav_file)  # 生成音频数据
            except Exception as e:
                logger.log_message(f"语音合成时出错: {str(e)}", level="ERROR")
                return jsonify({'status': 'error', 'message': '语音合成失败。'}), 500
            
            return jsonify({'status': 'success', 'audio_path': unique_filename, 'result_message': result_message})
        except ValueError as e:
            logger.log_message(f"解析响应失败: {str(e)}", level="ERROR")
        except Exception as e:
            logger.log_message(f"执行设备控制时出错: {str(e)}", level="ERROR")
        
        return jsonify({'status': 'success', 'message': f'Connected to gateway at {gateway_address}'})
    except Exception as e:
        logger.log_message(f"Error in handle_connect_gateway: {str(e)}", level="ERROR")  # Log the error
        return jsonify({'status': 'error', 'message': str(e)}), 500


def control_device(command_data):
    global sock  # 在这里也声明 sock 为全局变量
    """
    控制设备
    command_data: 包含控制命令的字典
    """
    try:
        if sock is None:
            logger.log_message("Socket 未连接，无法发送命令", level="ERROR")
            return "Socket 未连接，无法发送命令"

        # 获取拓扑信息
        logger.log_message("获取拓扑信息")
        devices = get_topology(sock)
        
        # 获取命令信息
        name = command_data.get('name')
        action = command_data.get('action')
        domain = command_data.get('domain')
        parameters = command_data.get('parameters')
        
        # 获取所有设备（nt=2）
        all_devices = [d for d in devices if d.get("nt") == 2]
        
        # 根据domain过滤设备类型（light对应type 1-4）
        if domain == "light":
            logger.log_message(f"查找网关下是否有 name 为: {name} 的设备")
            domain_devices = [d for d in all_devices if d.get("type") in [1, 2, 3, 4]]
        else:
            domain_devices = all_devices
        
        # 根据设备名称匹配设备
        filtered_devices = [
            dev for dev in domain_devices
            if dev.get("n") == name
        ]
        
        if not filtered_devices:
            logger.log_message(f"未找到符合条件的设备: {name}", level="ERROR")
            return f"未找到符合条件的设备: {name}"
            
        # 构建控制指令
        logger.log_message("构建控制指令")
        nodes = []
        for device in filtered_devices:
            node = {
                "id": device["id"],
                "nt": device["nt"],
                "set": {}
            }
            
            # 根据动作设置属性
            if action == "turn_on":
                node["set"]["p"] = True  # 使用布尔值 True
                logger.log_message(f"设备 {name} 将被打开。")
            elif action == "turn_off":
                node["set"]["p"] = False  # 使用布尔值 False
                logger.log_message(f"设备 {name} 将被关闭。")
            # 可以添加其他动作的处理...
            
            if parameters:
                node["set"].update(parameters)
                
            nodes.append(node)
            
        command = {
            "id": int(time.time()),
            "method": "gateway_set.prop",
            "nodes": nodes
        }
        logger.log_message(f"构建命令为: {command}")
        # 发送控制命令  
        logger.log_message("发送控制命令")
        send_command(sock, command)
        
        logger.log_message("命令已成功发送")
        return "命令已成功发送"
        
    except Exception as e:
        error_message = f"控制设备时出错: {str(e)}"
        logger.log_message(error_message, level="ERROR")
        return error_message


class MyModel(BaseModel):
    field: str

    @model_validator(mode='before')
    def check_field(cls, values):
        # Your validation logic here
        return values

@app.route('/scan_gateways', methods=['GET'])
def scan_gateways():
    global sock  # 声明 sock 为全局变量
    try:
        # 调用函数以仅扫描网关
        gateways = discover_gateway(socketio, scan_only=True)
        
        # 确保 discover_gateway 返回两个值
        sock, connected_gateway = discover_gateway(socketio, scan_only=False)
        
        return jsonify({'status': 'success', 'gateways': gateways, 'connected_gateway': connected_gateway})
    except Exception as e:
        logger.log_message(f"扫描网关时出错: {str(e)}", level="ERROR")
        return jsonify({'status': 'success', 'gateways': gateways, 'message': str(e)}), 500

if __name__ == '__main__':
    # 使用 eventlet 的 WSGI 服务器运行应用
    socketio.run(app, host='0.0.0.0', port=8888)  # 使用 HTTP 端口 