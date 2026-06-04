FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including LibreOffice for PDF conversion
RUN apt-get update && apt-get install -y \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
