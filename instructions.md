# Patent RAG Application - Docker Setup Instructions

## Overview

This document provides comprehensive instructions for setting up and running the Patent RAG (Retrieval-Augmented Generation) application using Docker with GPU acceleration.

## Architecture

The application consists of:
- **Patent Document Processing**: PDF text and image extraction
- **Vector Database**: Qdrant for semantic search
- **LLM Integration**: Ollama with LLaMA and LLaVA models
- **GPU Acceleration**: CUDA support for enhanced performance

## Docker Image Configuration

### Base Image
```dockerfile
FROM nvidia/cuda:13.0.0-cudnn-devel-ubuntu24.04
```

**Specifications:**
- **OS**: Ubuntu 24.04 (Debian-based)
- **CUDA Version**: 13.0.0
- **cuDNN**: Development version for deep learning
- **Python**: 3.x with pip support

### Build Process
1. **System Dependencies**: Install Python, build tools, and graphics libraries
2. **Python Environment**: Configure virtual environment and install dependencies
3. **Ollama Installation**: Download and configure Ollama for LLM inference
4. **Model Download**: Pre-download LLaMA and LLaVA models during build
5. **Application Setup**: Copy application files and configure startup script

## GPU Configuration

### Prerequisites
The host system must have:
- **NVIDIA GPU**: Compatible with CUDA 13.0
- **NVIDIA Drivers**: Latest stable version
- **NVIDIA Container Toolkit**: Required for Docker GPU access

### NVIDIA Container Toolkit Installation

**Purpose**: Enables GPU acceleration within Docker containers by providing runtime components and libraries to interface with NVIDIA GPUs.

**Installation Steps**:
1. Add NVIDIA package repositories
2. Install `nvidia-docker2` package
3. Restart Docker daemon
4. Verify installation with `docker run --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi`

**Official Documentation**: [NVIDIA Container Toolkit Installation Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

### Docker GPU Access
```bash
# Run container with GPU access
docker run --gpus all -v $(pwd):/app patent-rag:v1.0

# Using docker-compose
docker-compose up --build
```

## Application Components

### 1. Document Processing
- **PyMuPDF**: PDF text extraction
- **EasyOCR**: Image text recognition
- **OpenCV**: Image processing and analysis

### 2. Vector Database
- **Qdrant**: High-performance vector similarity search
- **Sentence Transformers**: Text embedding generation

### 3. LLM Integration
- **Ollama**: Local LLM inference engine
- **LLaMA 3**: Text generation model
- **LLaVA**: Multimodal (text + image) model

## API Integration

### FastAPI Server Implementation
The application will be enhanced with a FastAPI server to enable:
- **RESTful API**: HTTP endpoints for patent processing
- **Remote Invocation**: Trigger processing from external systems
- **File Upload**: Accept patent PDFs via API requests
- **Result Retrieval**: Return processed results via JSON responses

**Implementation Plan**:
```python
# Example API structure
@app.post("/process_patent")
async def process_patent(pdf_path: str):
    return await main(pdf_path)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

## Container Registry

### GitHub Container Registry Setup
To enable public access to the Docker image:

1. **Repository Configuration**:
   - Enable GitHub Actions for automated builds
   - Configure secrets for registry authentication
   - Set up automated testing and validation

2. **Image Publishing**:
   - Tag images with semantic versions
   - Push to GitHub Container Registry
   - Document usage instructions

3. **Public Access**:
   - Make repository public
   - Provide pull instructions
   - Include example usage

### Usage Instructions
```bash
# Pull from GitHub Container Registry
docker pull ghcr.io/username/patent-rag:latest

# Run with GPU support
docker run --gpus all -v $(pwd):/data ghcr.io/username/patent-rag:latest
```

## Development Workflow

### Local Development
1. **Build Image**: `docker build -t patent-rag:v1.0 .`
2. **Run Container**: `docker run -it --gpus all -v $(pwd):/app patent-rag:v1.0`
3. **Interactive Mode**: Access bash shell for debugging
4. **Volume Mounting**: Mount local files for development

### Production Deployment
1. **Image Optimization**: Multi-stage builds for smaller images
2. **Security**: Non-root user, minimal dependencies
3. **Monitoring**: Health checks and logging
4. **Scaling**: Container orchestration with Kubernetes

## Troubleshooting

### Common Issues
1. **GPU Not Detected**: Verify NVIDIA Container Toolkit installation
2. **Model Download Failures**: Check network connectivity and disk space
3. **Memory Issues**: Adjust container memory limits for large models
4. **Permission Errors**: Ensure proper file permissions and user configuration

### Debug Commands
```bash
# Check GPU access
nvidia-smi

# Verify Ollama installation
ollama --version

# List downloaded models
ollama list

# Check container logs
docker logs <container_id>
```

## Performance Considerations

### GPU Utilization
- **Memory**: LLaVA model requires ~8GB GPU memory
- **Batch Processing**: Optimize for multiple patent processing
- **Caching**: Implement result caching for repeated queries

### Optimization Strategies
- **Model Quantization**: Use quantized models for faster inference
- **Parallel Processing**: Process multiple documents concurrently
- **Resource Limits**: Set appropriate CPU and memory limits

## Security Considerations

### Container Security
- **Non-root User**: Run application as non-privileged user
- **Image Scanning**: Regular vulnerability scanning
- **Dependency Updates**: Keep dependencies updated
- **Network Security**: Restrict container network access

### Data Privacy
- **Local Processing**: All processing occurs within container
- **No External Calls**: Models run locally without internet dependency
- **Data Isolation**: Proper volume mounting and cleanup
