FROM python:3.12-slim

WORKDIR /app

# Install Java (required for Aspose.Words JAR via JPype)
RUN apt-get update && apt-get install -y \
    fontconfig \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
