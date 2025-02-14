# Stage 1: 构建阶段，使用官方 Python 3.8 镜像
FROM python:3.8 AS builder

# 安装必要的依赖及工具
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
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
RUN python -c "import whisper; whisper.load_model('base')"

# Stage 2: 运行阶段，基于轻量级 Python Alpine 镜像（已包含 Python 环境）
FROM python:3.8-alpine

# 安装 nginx、Supervisor 以及其他必要工具
RUN apk update && apk add --no-cache \
    nginx \
    supervisor \
    ffmpeg \
    libsndfile \
    && rm -rf /var/cache/apk/*

# 复制 Nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制 SSL 证书（如果需要）
COPY ssl /etc/nginx/ssl

# 复制 Supervisor 配置文件
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 从构建阶段复制整个应用程序文件（包括已安装的依赖）
COPY --from=builder /app /app

# 设置工作目录
WORKDIR /app

# 暴露应用及 Nginx 所需端口
EXPOSE 80 443 8888

# 使用 Supervisor 作为入口，管理 Python 应用和 Nginx
CMD ["/usr/bin/supervisord", "-n"]
