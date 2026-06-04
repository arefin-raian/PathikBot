FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including LibreOffice for PDF conversion
RUN apt-get update && apt-get install -y \
    fontconfig \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install SutonnyMJ fonts for PDF generation (LibreOffice needs them to render Bangla)
COPY fonts/ /tmp/fonts/
RUN mkdir -p /usr/local/share/fonts/truetype/sutonnymj \
    && cp /tmp/fonts/*.ttf /usr/local/share/fonts/truetype/sutonnymj/ \
    && fc-cache -fv \
    && rm -rf /tmp/fonts

COPY . .

CMD ["python", "-m", "bot.main"]
