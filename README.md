# Hexafalls 2K25 🎬

A modern, scalable video processing pipeline built with Flask that downloads, processes, transcribes, and uploads video chunks from Cloudflare R2 storage. Designed for real-time video conference recording processing with AI-powered transcription.

## 🚀 Overview

Hexafalls 2K25 is a production-ready Flask web service that processes video and audio chunks into professional-quality media files with embedded transcriptions. The system features a RESTful API for seamless integration with video conferencing platforms and real-time processing capabilities.

### Key Features

- 🎥 **Professional Video Processing**: Converts WebM chunks to high-quality MP4 with H.264 encoding
- 🎤 **AI-Powered Transcription**: OpenAI Whisper integration with multiple model sizes
- 🌐 **RESTful API**: Easy integration with existing systems
- ☁️ **Cloud Storage**: Seamless Cloudflare R2 integration
- 🔄 **Asynchronous Processing**: Non-blocking pipeline execution
- 📱 **Soft Subtitles**: Embedded captions in MP4 containers
- 🛡️ **Error Handling**: Robust error recovery and logging

## 🏗️ Architecture

```
├── Flask Web Service
│   ├── RESTful API Endpoints
│   ├── Asynchronous Processing
│   └── Configuration Management
├── Video Processing Pipeline
│   ├── Chunk Download & Validation
│   ├── FFmpeg-based Processing
│   ├── Whisper AI Transcription
│   └── Cloud Upload
└── Storage Layer
    ├── Cloudflare R2 (Primary)
    └── Local Temporary Storage
```

## 🔧 Tech Stack

- **Flask 3.1+**: Modern Python web framework
- **Python 3.12+**: Core programming language
- **FFmpeg**: Professional video/audio processing
- **OpenAI Whisper**: State-of-the-art speech recognition
- **Cloudflare R2**: S3-compatible object storage
- **boto3**: AWS SDK for Python (R2 integration)
- **Threading**: Asynchronous task processing

## ⚙️ Installation

### Prerequisites

- Python 3.12 or higher
- FFmpeg installed and accessible in PATH
- Cloudflare R2 account and credentials

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/hexafalls2k25.git
   cd hexafalls2k25
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install FFmpeg:**
   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   
   # Windows (using chocolatey)
   choco install ffmpeg
   ```

5. **Configure environment variables:**
   Create a `.env` file in the project root:
   ```env
   S3_ACCESS_KEY_ID=your_r2_access_key
   S3_SECRET_ACCESS_KEY=your_r2_secret_key
   ACCOUNT_ID=your_cloudflare_account_id
   S3_BUCKET_NAME=your_r2_bucket_name
   ```

## 🚀 Quick Start

### Start the Flask Service

```bash
# Development mode
flask run

# Production mode with custom host/port
flask run --host=0.0.0.0 --port=5000

# Using Python directly
python run.py
```

### API Usage

#### Submit Processing Job

```bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": "meeting_123",
    "take": "1",
    "user_id": "user_456",
    "whisper_model": "base",
    "cleanup": true,
    "skip_transcription": false
  }'
```

#### Check Service Status

```bash
curl http://localhost:5000/status
```

## 📡 API Reference

### POST `/submit`

Initiates video processing pipeline for specified meeting chunks.

**Request Body:**
```json
{
  "meeting_id": "string (required)",
  "take": "string (required)", 
  "user_id": "string (required)",
  "whisper_model": "string (optional, default: 'base')",
  "cleanup": "boolean (optional, default: true)",
  "skip_transcription": "boolean (optional, default: false)"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Video processing pipeline started",
  "meeting_id": "meeting_123",
  "take": "1",
  "user_id": "user_456",
  "config": {
    "REMOTE_DIR": "recordings/meeting_123/1/user_456",
    "LOCAL_DIR": "../chunks/meeting_123/1/user_456",
    "OUTPUT_DIR": "../recordings/meeting_123/1/user_456",
    "UPLOAD_DIR": "recordings/meeting_123/1"
  },
  "options": {
    "whisper_model": "base",
    "cleanup": true,
    "skip_transcription": false
  }
}
```

### GET `/status`

Returns service health status.

**Response:**
```json
{
  "status": "running",
  "message": "Video processing service is running"
}
```

## 🔄 Processing Pipeline

### 1. **Initialization & Configuration**
   - Validate API request parameters
   - Configure directory structures
   - Initialize processing components

### 2. **Chunk Download**
   - Connect to Cloudflare R2 storage
   - Download video/audio chunks by prefix
   - Organize files by type (video/audio)

### 3. **Video Processing**
   - Concatenate WebM video chunks
   - Fix timestamp inconsistencies
   - Convert to H.264 MP4 format

### 4. **Audio Processing**
   - Concatenate WebM audio chunks
   - Extract to WAV format for transcription
   - Encode to AAC for final output

### 5. **AI Transcription** (Optional)
   - Load Whisper model (tiny/base/small/medium/large)
   - Generate timestamped transcription
   - Create SRT subtitle files
   - Export JSON metadata

### 6. **Final Assembly**
   - Mux video, audio, and subtitles
   - Embed soft captions in MP4 container
   - Optimize for web delivery

### 7. **Upload & Cleanup**
   - Upload processed files to R2
   - Standardized naming convention
   - Clean temporary files (optional)

## 🎛️ Configuration Options

### Whisper Models
- `tiny`: Fastest, lowest accuracy (~1GB VRAM)
- `base`: Balanced performance (default, ~1GB VRAM)
- `small`: Better accuracy (~2GB VRAM)
- `medium`: High accuracy (~5GB VRAM)
- `large`: Best accuracy (~10GB VRAM)

### Processing Options
- `cleanup`: Remove temporary files after processing
- `skip_transcription`: Skip AI transcription step
- Custom output directories and naming

## 📁 Project Structure

```
hexafalls2k25/
├── app/                    # Flask application package
│   ├── __init__.py        # Flask app initialization
│   ├── routes.py          # API endpoint definitions
│   ├── worker.py          # Core processing pipeline
│   ├── driver.py          # Configuration management
│   └── chunksToVideo.py   # Standalone video processor
├── run.py                 # Flask application entry point
├── config.py              # Application configuration
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not tracked)
├── README.md              # This file
└── .gitignore            # Git ignore rules
```

## 🐳 Docker Deployment

```dockerfile
FROM python:3.12-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Run Flask application
CMD ["flask", "run", "--host=0.0.0.0"]
```

## 🔧 Development

### Local Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Run with debug mode
export FLASK_ENV=development
flask run --debug

# Run tests (if available)
python -m pytest
```

### Standalone Processing

For local testing without the Flask API:

```bash
# Process local chunks directly
python app/chunksToVideo.py

# Test R2 connectivity
python accessR2.py
```

## 🚨 Troubleshooting

### Common Issues

1. **FFmpeg not found**: Ensure FFmpeg is installed and in PATH
2. **R2 connection failed**: Verify credentials in `.env` file
3. **Whisper model loading**: Check available VRAM for larger models
4. **Chunk not found**: Verify correct meeting_id/take/user_id combination

### Debug Mode

Enable detailed logging:
```bash
export FLASK_ENV=development
flask run --debug
```

## 📊 Performance

### Processing Times (Approximate)
- **10 minutes of video**: ~2-5 minutes processing
- **Whisper transcription**: +30-60 seconds per minute of audio
- **Upload speed**: Depends on bandwidth and file size

### Resource Requirements
- **CPU**: Multi-core recommended for FFmpeg
- **RAM**: 2-4GB base + Whisper model size
- **Storage**: 3x source file size during processing
- **Network**: Stable connection for R2 operations

## 🛡️ Security

- Environment variables for sensitive credentials
- Input validation on all API endpoints
- Secure temporary file handling
- Automatic cleanup of processed files

## 👥 Contributors

**Team Bolts**
- [Sk Sameer Salam](https://github.com/dampdigits) - Lead Developer
- [Tushar Daiya](https://github.com/tushar-daiya/) - Backend Engineer
- [Sougata Mandal](https://github.com/SougataXdev) - DevOps Engineer
- [Aquib Alam](https://github.com/aquib399) - Frontend Integration

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

For support, feature requests, or bug reports, please open an issue on GitHub.