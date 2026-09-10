FROM python:3.12-slim

# Claude Agent SDK запускает Claude Code CLI как подпроцесс — нужен Node.
# git/ripgrep/curl нужны самому агенту для работы с кодом и файлами.
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs npm git curl ca-certificates ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

CMD ["python", "-m", "bot.main"]
