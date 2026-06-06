FROM python:3.12-slim

WORKDIR /app

# Install Java 17 (required for Aspose.Words JAR via JPype)
# Install Playwright system dependencies (required for headless Chromium)
RUN apt-get update && apt-get install -y \
    fontconfig \
    openjdk-17-jre-headless \
    libnss3 libatk-bridge2.0-0 libdrm-dev libxkbcommon-dev \
    libgbm-dev libasound2 libxshmfence-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN python -m playwright install chromium

COPY . .

CMD ["python", "-m", "bot.main"]
