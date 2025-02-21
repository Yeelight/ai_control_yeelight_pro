from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from typing import List, Dict
import whisper
import opencc
import os
import warnings
import soundfile as sf  # For reading and writing audio files
from pydub import AudioSegment
from ollama_api import initialize_llm
from utils import extract_json
from gateway import get_topology, discover_gateway, connect_to_gateway, control_device
from pydantic import BaseModel, model_validator
from logger import init_logger, get_logger  # 在需要时获取 Logger 实例  # 导入初始化函数
from prompts import prompt  # Import the prompt variable from prompts.py
from datetime import datetime
from config import *  # 导入配置文件中的环境变量
from piper import PiperVoice
import uuid
import wave

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

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

# Global variables to hold the gateway_socket and gateway address
gateway_sock = None
gateway_address = None
connected_gateway = None  # 全局变量保存连接的网关信息

# 初始化 Logger
init_logger(socketio)

logger = get_logger()  # 在需要时获取 Logger 实例

# Function to log messages
def log_message(level, message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"***** [{level}] [{timestamp}] {message} *****\n"
    # Add your logging logic here

# 全局变量用于缓存拓扑信息
cached_topology = None

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
    data = request.get_json()
    user_input = data.get('user_input')  # Get user input
    try:
        logger.log_message("Using Ollama local model: " + llm.base_url + "/" + llm.model)
        
        # Get model output (streaming)
        logger.log_message("Ollama model response start")
        full_response = []
        for chunk in chain.stream(user_input):
            logger.log_message_stream(chunk)
            full_response.append(chunk)
        logger.log_message_stream("\n")
        print("\n***** Ollama model response end *****")
        
        # Merge response content
        response = ''.join(full_response)
        
        # Parse response to JSON
        try:
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
        except ValueError as e:
            logger.log_message(f"Failed to parse response: {str(e)}", level="ERROR")
        except Exception as e:
            logger.log_message(f"Error during device control: {str(e)}", level="ERROR")
        
        return jsonify({'status': 'success', 'message': f'Connected to gateway at {gateway_address}'})
    except Exception as e:
        logger.log_message(f"Error in handle_connect_gateway: {str(e)}", level="ERROR")  # Log the error
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
        return jsonify({
            'status': 'success',
            'nodes': topology
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8888) 