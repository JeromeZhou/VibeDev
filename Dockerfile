FROM python:3.12-slim

WORKDIR /app

# 系统依赖（Playwright 浏览器需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 浏览器（仅 chromium，节省空间）
RUN playwright install --with-deps chromium

COPY . .

# 数据目录
RUN mkdir -p data/raw data/db outputs/pphi_rankings outputs/reports

# Web 端口
EXPOSE 9000

# 默认启动 Web 服务
CMD ["uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "9000"]
