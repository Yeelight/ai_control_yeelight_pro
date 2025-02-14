# Stage 1: 构建阶段
FROM python:3.8-slim AS builder

# 安装必要的依赖及工具
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
    libopenblas-dev \
    libffi-dev \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# 升级 pip
RUN pip install --no-cache-dir --upgrade pip

# 设置工作目录
WORKDIR /app

# 复制依赖清单并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用程序代码
COPY . .

# 预下载并缓存 Whisper 模型（可选）
RUN python -c "import whisper; whisper.load_model('base')"

# Stage 2: 运行阶段，基于轻量级 Alpine Linux 的 nginx 镜像
FROM nginx:alpine

# 安装 Supervisor 用于进程管理
RUN apk update && apk add --no-cache supervisor

# 复制 Nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制 SSL 证书（如果需要）
COPY ssl /etc/nginx/ssl

# 复制构建阶段生成的应用程序文件
COPY --from=builder /app /app

# 复制 Supervisor 配置文件
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 设置工作目录
WORKDIR /app

# 暴露应用及 Nginx 所需端口（根据实际情况调整）
EXPOSE 80 443 8888

# 使用 Supervisor 作为入口，管理 Python 应用和 Nginx
CMD ["/usr/bin/supervisord", "-n"]
