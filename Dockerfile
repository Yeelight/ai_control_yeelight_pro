# 使用官方 Python 镜像作为基础镜像
FROM python:3.8-slim

# 安装必要的依赖
RUN apt-get update && apt-get install -y --fix-missing \
    ffmpeg \
    libsndfile1 \
    build-essential \
    libopenblas-dev \
    libffi-dev \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖清单并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用程序代码
COPY . .

# 预下载并缓存 Whisper 模型（可选）
# RUN python -c "import whisper; whisper.load_model('base')"


# 复制 SSL 证书和密钥
COPY cert.pem /app/cert.pem
COPY key.pem /app/key.pem

# 暴露 HTTPS 端口
EXPOSE 443

# 运行 Flask 应用
CMD ["python", "app.py"]
