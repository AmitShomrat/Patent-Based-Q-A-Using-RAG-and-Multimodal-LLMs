# Use NVIDIA CUDA base image with Python
FROM pytorch/pytorch:2.2.2-cuda12.1-cudnn8-devel

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0

# Install system dependencies and Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for python
RUN ln -sf /usr/bin/python3 /usr/bin/python
RUN ln -sf /usr/bin/pip3 /usr/bin/pip

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt || true

# Create directory for models and data
RUN mkdir -p /app/models /app/data

# Start Ollama service and download models in a single RUN command
RUN ollama serve & \
sleep 15 && \
ollama pull llama3:latest && \
ollama pull llava:7b && \
pkill ollama

# Copy application files
COPY . .

# Expose port (adjust if your app uses a different port)
EXPOSE 8000

# Create startup script (without model downloading)
RUN echo '#!/bin/bash\n\
# Start Ollama service in background\n\
ollama serve &\n\
\n\
# Wait for Ollama to start\n\
sleep 5\n\
\n\
# Run the main application\n\
fastapi dev --host 0.0.0.0 --port 8000 Server_RAG.py' > /app/start.sh && chmod +x /app/start.sh

# Set default command
CMD ["/app/start.sh"]
