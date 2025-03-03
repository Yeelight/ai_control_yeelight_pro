#!/bin/bash

# 检查 Homebrew 是否已安装
if ! command -v brew &> /dev/null
then
    echo "Homebrew 未安装，正在安装..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "Homebrew 已安装"
fi

# 检查 Python 3.10 是否已安装
if ! /opt/homebrew/bin/python3.10 --version &> /dev/null
then
    echo "Python 3.10 未安装，正在安装..."
    brew install python@3.10
else
    echo "Python 3.10 已安装"
fi

# 检查 ffmpeg 是否已安装
if ! command -v ffmpeg &> /dev/null
then
    echo "ffmpeg 未安装，正在安装..."
    brew install ffmpeg
else
    echo "ffmpeg 已安装"
fi


# 克隆项目
echo "克隆项目..."
cd ~/ai_home_control_space
if [ ! -d "ai_control_yeelight_pro" ]; then
    git clone https://github.com/Yeelight/ai_control_yeelight_pro.git
fi
cd ai_control_yeelight_pro

# 创建 Python 虚拟环境
echo "创建 Python 虚拟环境..."
/opt/homebrew/bin/python3.10 -m venv venv

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装项目依赖
echo "安装项目依赖..."
/opt/homebrew/opt/python@3.10/bin/pip3.10 install piper-tts --no-deps piper-phonemize-cross onnxruntime numpy
/opt/homebrew/opt/python@3.10/bin/pip3.10 install -r requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple

# 启动 Flask 应用程序
echo "启动 Flask 应用程序..."
/opt/homebrew/bin/python3.10 app.py