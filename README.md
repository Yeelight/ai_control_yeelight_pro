# Ai Home Control

## 项目简介
这是一个基于 Flask 的智能家居控制系统，使用 Whisper 进行语音识别，并通过 Ollama 模型进行设备控制。

## 环境要求
- Python 3.7 或更高版本
- pip

## 安装步骤

1. **克隆项目**
   ```bash
   git clone <your-repo-url>
   cd <your-repo-directory>
   ```

2. **创建虚拟环境（可选）**
   ```bash
   python -m venv venv
   source venv/bin/activate  # 在 Windows 上使用 venv\Scripts\activate
   ```

3. **安装依赖**
   使用 `pip` 安装项目所需的依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**
   在项目根目录下创建一个 `config.py` 文件，并设置 Whisper 模型大小：
   ```python
   import os

   # Set the Whisper model size
   os.environ['WHISPER_MODEL_SIZE'] = 'base'  # 可以根据需要更改为 'small', 'medium', 'large' 等
   ```

5. **运行应用**
   启动 Flask 应用：
   ```bash
   python app.py
   ```

6. **访问应用**
   打开浏览器并访问 `http://127.0.0.1:5000`。

## 使用说明
- 点击"开始录音"按钮进行语音输入。
- 录音完成后，系统将自动处理音频并返回转录结果。
- 使用 Ollama 模型进行设备控制。

## 贡献
欢迎任何形式的贡献！请提交问题或拉取请求。

## 许可证
本项目采用 MIT 许可证，详细信息请查看 LICENSE 文件。
