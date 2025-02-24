from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from typing import List, Dict
import whisper
import opencc
import os
import warnings
import soundfile as sf  # For reading and writing audio files
from pydub import AudioSegment
from ollama_api import initialize_llm
from utils import extract_json  # 确保 utils.py 中的 extract_json 是普通函数
from gateway import get_topology, discover_gateway, connect_to_gateway, control_device, nt_type_mapping
from pydantic import BaseModel, model_validator
from logger import init_logger, get_logger  # 在需要时获取 Logger 实例  # 导入初始化函数
from prompts import template  # Import the prompt variable from prompts.py
from config import *  # 导入配置文件中的环境变量
from piper import PiperVoice
import uuid
import wave
from database_manager import DatabaseManager, NodeInfo
from collections import defaultdict
import json

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 定义模型和配置文件的路径
model_path = "tts/zh_CN-huayan-medium.onnx"
config_path = "tts/zh_CN-huayan-medium.onnx.json"

db_manager = DatabaseManager()
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

# 在文件顶部添加自定义异常
class OutputValidationError(Exception):
    """自定义输出验证异常"""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message



# 将普通函数包装成 Runnable
json_parser = RunnableLambda(extract_json)

# 带重试的解析器
_retry_parser = json_parser.with_retry(
    stop_after_attempt=3,
    wait_exponential_jitter=False
)


# Define the prompt variable before using it
# prompt is now imported from prompts.py
prompt_template = PromptTemplate(
    template=template,
    input_variables=["user_input", "node_info"]  # 确保变量名匹配
)

# 修改处理链结构
chain = (
     RunnableParallel({
                "user_input": RunnablePassthrough(),
                "node_info": RunnablePassthrough()
            })
    | prompt_template 
    | llm 
)

# Global variables to hold the gateway_socket and gateway address
gateway_sock = None
gateway_address = None
connected_gateway = None  # 全局变量保存连接的网关信息

# 初始化 Logger
init_logger(socketio)

logger = get_logger()  # 在需要时获取 Logger 实例


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
    logger.log_message("Original Transcription (Traditional):", result['text'])

    # 使用 OpenCC 将繁体字转换为简体字
    converter = opencc.OpenCC('t2s')  # t2s.json: 繁体转简体的配置文件
    simplified_text = converter.convert(result['text'])

    return jsonify({'text': simplified_text})

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json()
    user_input = data.get('user_input')  # Get user input
    

    try:
        logger.log_message(f"使用的 ollama 本地模型为: {llm.base_url}/{llm.model}")

        node_info_response = db_manager.query_nodes()
        # 执行处理链
        full_response = []
        input_variables = {"user_input": user_input, "node_info": format_node_info_for_llm(node_info_response)}
        prompt = prompt_template.format(**input_variables)
        # 执行处理链
        full_response = []
        for chunk in chain.stream(prompt):  
            # 直接处理字符串块
            logger.log_message_stream(chunk)
            full_response.append(chunk)
        
        # 合并为完整 JSON 字符串
        response = ''.join(full_response)
        command_data = extract_json(response)
        
        result_message = control_device(command_data, socketio) if command_data else "Invalid command data"
        
        # Use Piper for speech synthesis, convert result message to audio file
        voice = PiperVoice.load(model_path, config_path=config_path)
        unique_filename = f'static/result_audio_{uuid.uuid4()}.wav'  # Generate unique filename
        
        # Synthesize speech and write to WAV file
        try:
            # Call synthesize method to generate audio data
            with wave.open(unique_filename, 'wb') as wav_file:  # Open WAV file to write
                voice.synthesize(result_message, wav_file)  # Generate audio data
        except Exception as e:
            logger.log_message(f"Error during speech synthesis: {str(e)}", level="ERROR")
            return jsonify({'status': 'error', 'message': 'Speech synthesis failed.'}), 500
        
        return jsonify({'status': 'success', 'audio_path': unique_filename, 'result_message': result_message})
    except Exception as e:
        logger.log_message(f"Error in Ollama model response: {str(e)}", level="ERROR")  # Log the error
        return jsonify({'status': 'error', 'message': str(e)}), 500

class MyModel(BaseModel):
    field: str

    @model_validator(mode='before')
    def check_field(cls, values):
        # Your validation logic here
        return values

@app.route('/scan_and_connect', methods=['GET'])
def scan_and_connect():
    try:
        gateways = discover_gateway(socketio, scan_only=True)  # 同步调用
        connected_gateway = connect_to_gateway({'ip': gateways[0]['ip']}, socketio)  # 同步调用
        return jsonify({
            'status': 'success',
            'connected_gateway': connected_gateway
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_topology', methods=['GET'])
def get_topologys():
    try:
        topology = get_topology(socketio)
        db_manager.save_node_info_bulk(topology)  # Ensure this is called with the correct argument
        return jsonify({
            'status': 'success',
            'nodes': topology
        })
    except Exception as e:
        logger.log_message(f"Error in get_topology: {str(e)}", level="ERROR")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def format_node_info_for_llm(node_info_response: List[NodeInfo]) -> str:
    """
    将节点信息格式化为指定结构的文本
    参数:
        node_info_response: 节点信息列表
    返回:
        格式化后的多行字符串，包含标准分组和设备列表
    """
    node_groups = defaultdict(list)
    result_strings = []

    # 第一遍遍历：建立分组索引
    for node in node_info_response:
        node_groups[node.type_description].append(node)

    # 第二遍遍历：生成格式化文本
    for group_name, nodes in node_groups.items():
        # 添加分组标题
        result_strings.append(f" '{group_name}'数据包含:")
        # 生成节点列表
        result_strings.extend([f"- {node.name}" for node in nodes])
        # 添加空行保持分组间距
        result_strings.append("")

    return '\n'.join(result_strings).strip()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8888) 