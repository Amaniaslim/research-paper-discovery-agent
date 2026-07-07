# Research Paper Discovery Agent - Streamlit app
# Clean, slim Python base image.
FROM python:3.12-slim

# Streamlit / runtime settings
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# System deps:
# - tesseract-ocr: enables local OCR for scanned PDFs (OCR stays optional at runtime)
# - libgl1 / libglib2.0-0: runtime libs used by PyMuPDF / Pillow image handling
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application code.
COPY . .

# Data / output directories used as mount points.
RUN mkdir -p data/pdfs demo_output

EXPOSE 8501

# Basic container healthcheck against Streamlit's health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)" || exit 1

CMD ["streamlit", "run", "app_sprint3.py", "--server.port=8501", "--server.address=0.0.0.0"]
