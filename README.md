# Hexafalls-2k25

A robust video processing pipeline for downloading, concatenating, transcribing, and uploading video and audio chunks from Cloudflare R2 storage.

## 🚀 Overview

Hexafalls2k25 is a comprehensive solution for processing video and audio chunks into complete, polished media files with transcription. The pipeline handles everything from downloading raw chunks to creating professional-quality MP4 videos with embedded captions.

## 🔧 Tech Stack

- **Python 3**: Core programming language
- **FFmpeg**: Video and audio processing
- **Cloudflare R2**: S3-compatible storage for input/output files
- **OpenAI Whisper**: AI-powered audio transcription
- **boto3**: AWS SDK for Python (for R2 integration)
- **dotenv**: Environment variable management

## ⚙️ Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/hexafalls2k25.git
   cd hexafalls2k25
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install FFmpeg if not already available:
   ```bash
   # For Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # For macOS
   brew install ffmpeg
   ```

4. Create a .env file with your Cloudflare R2 credentials:
   ```
   S3_ACCESS_KEY_ID=your_access_key
   S3_SECRET_ACCESS_KEY=your_secret_key
   ACCOUNT_ID=your_cloudflare_account_id
   S3_BUCKET_NAME=your_bucket_name
   ```

## 📋 Usage

### Basic Usage

Run the main worker script to process video and audio chunks:

```bash
python worker.py
```

### Advanced Options

```bash
# Use a different Whisper model
python worker.py --whisper-model medium

# Skip cleanup of temporary files
python worker.py --no-cleanup

# Skip audio transcription
python worker.py --no-transcript

# Combine options
python worker.py --whisper-model large --no-cleanup
```

### Process Local Files Only

If you already have chunks downloaded and just want to process them:

```bash
python chunksToVideo.py
```

## 🔄 Process Flow

1. **Configuration Setup**:
   - Load environment variables
   - Set up paths and directories

2. **Download Phase**:
   - Connect to Cloudflare R2
   - Download video and audio chunks
   - Sort into appropriate directories

3. **Processing Phase**:
   - Concatenate video chunks
   - Concatenate audio chunks
   - Convert audio to WAV format

4. **Transcription Phase**:
   - Load Whisper AI model
   - Transcribe audio
   - Generate SRT subtitle file

5. **Muxing Phase**:
   - Create final MP4 with H.264 video codec
   - Embed audio with AAC codec
   - Add soft subtitles in MOV_TEXT format

6. **Upload Phase**:
   - Upload processed video, audio, and transcript files to R2
   - Use standardized naming convention

7. **Cleanup Phase** (optional):
   - Remove temporary files and directories

## 📁 Project Structure

- worker.py: Main pipeline script
- driver.py: Configuration settings
- chunksToVideo.py: Standalone video processing
- accessR2.py: R2 storage access utilities
- .env: Environment variables (not tracked in git)
- requirements.txt: Python dependencies
- chunks: Directory for downloaded chunks
- recordings: Output directory for processed files

## 👥 Contributors

**Team: Bolts**
1. [Sk Sameer Salam](https://github.com/dampdigits)
2. [Tushar Daiya](https://github.com/tushar-daiya/)
3. [Sougata Mandal](https://github.com/SougataXdev)
4. [Aquib Alam](https://github.com/aquib399)

---

For more information, please open an issue or contact the maintainers.