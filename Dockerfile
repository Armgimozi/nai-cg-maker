FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# 태그 사전 다운로드(이미지에 포함). 빌드 시 인터넷 필요.
RUN python fetch_tags.py

ENV PORT=7860
EXPOSE 7860
# 이미지 생성은 길어질 수 있으므로 타임아웃을 넉넉히.
CMD gunicorn --bind 0.0.0.0:${PORT:-7860} --timeout 300 --workers 2 wsgi:app
