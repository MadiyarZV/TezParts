FROM python:3.12-slim

# Claude Agent SDK запускает Claude Code как подпроцесс — нужен Node.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot

CMD ["python", "-m", "bot.main"]
