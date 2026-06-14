FROM python:3.12-slim

WORKDIR /app

# Install Java (Aspose.Words via JPype) + LibreOffice (fallback PDF converter)
RUN apt-get update && apt-get install -y \
    fontconfig \
    openjdk-21-jre-headless \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

# Auto-detect Java home so _find_jvm_dll() finds libjvm.so immediately
RUN JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java)))) && \
    echo "Detected JAVA_HOME=$JAVA_HOME" && \
    echo "export JAVA_HOME=$JAVA_HOME" >> /etc/profile.d/java.sh
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs the Telegram bot in a background thread AND the FastAPI web API
# (uvicorn) in the foreground bound to $PORT. To run only the bot
# (no web API), override the command with: python -m bot.main
CMD ["python", "-m", "web_api.launcher"]
