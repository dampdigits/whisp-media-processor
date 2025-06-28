#!/usr/bin/env python3
"""
Complete video processing pipeline:
1. Set up configuration and directories
2. Download chunks from Cloudflare R2
3. Process chunks into video/audio files
4. Generate transcript using Whisper
5. Upload final files back to R2
"""

import os
import sys
import subprocess
import boto3
from botocore.client import Config
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
import json
import whisper

# Configuration - you can modify these
MEETING_ID = "abcdef"
TAKE = "some-take-id"
USER_ID = "some-user-id"

PREFIX = "recordings"
DIR = '/'.join([MEETING_ID, TAKE, USER_ID])

REMOTE_DIR = PREFIX+"/"+DIR
LOCAL_DIR = "./chunks/"+DIR
OUTPUT_DIR = "./recordings/"+DIR
UPLOAD_DIR = PREFIX+"/"+'/'.join([MEETING_ID, TAKE])

print(f"Remote Directory: {REMOTE_DIR}")

class CloudflareR2Manager:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Get credentials from environment variables
        self.ACCESS_KEY = os.getenv('S3_ACCESS_KEY_ID')
        self.SECRET_KEY = os.getenv('S3_SECRET_ACCESS_KEY')
        self.ACCOUNT_ID = os.getenv('ACCOUNT_ID')
        self.BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
        
        if not all([self.ACCESS_KEY, self.SECRET_KEY, self.ACCOUNT_ID, self.BUCKET_NAME]):
            raise ValueError("❌ Missing required environment variables. Please check your .env file.")
        
        self.ENDPOINT_URL = f"https://{self.ACCOUNT_ID}.r2.cloudflarestorage.com"
        
        # Create S3-compatible client for Cloudflare R2
        self.s3 = boto3.client('s3',
            aws_access_key_id=self.ACCESS_KEY,
            aws_secret_access_key=self.SECRET_KEY,
            endpoint_url=self.ENDPOINT_URL,
            config=Config(signature_version="s3v4"),
            region_name='auto'
        )
    
    def download_chunks(self):
        """Download chunks from R2 storage"""
        print(f"🌐 Downloading chunks from R2...")
        print(f"📂 Remote directory: {REMOTE_DIR}")
        print(f"📂 Local directory: {LOCAL_DIR}")
        
        try:
            response = self.s3.list_objects_v2(Bucket=self.BUCKET_NAME, Prefix=REMOTE_DIR)
            
            if 'Contents' not in response:
                print("❌ No chunks found in remote directory!")
                return False
            
            downloaded_count = 0
            for obj in response.get("Contents", []):
                file = obj['Key'].split('/')[-1]
                chunkType = file.split('.')[0].split('_')[0]
                
                if chunkType == "audio":
                    DOWNLOAD_FOLDER = "/audio"
                else:
                    DOWNLOAD_FOLDER = "/video"
                
                DOWNLOAD_DIR = LOCAL_DIR + DOWNLOAD_FOLDER
                
                # Create directory if it doesn't exist
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                
                # Full path for the downloaded file
                local_file_path = os.path.join(DOWNLOAD_DIR, file)
                
                # Download file (will overwrite if exists)
                print(f"📥 Downloading: {obj['Key']} -> {local_file_path}")
                self.s3.download_file(self.BUCKET_NAME, obj['Key'], local_file_path)
                downloaded_count += 1
            
            print(f"✅ Downloaded {downloaded_count} chunks successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error downloading chunks: {e}")
            return False
    
    def upload_file(self, local_path, remote_key):
        """Upload a file to R2 storage"""
        try:
            print(f"📤 Uploading: {local_path} -> {remote_key}")
            self.s3.upload_file(str(local_path), self.BUCKET_NAME, remote_key)
            return True
        except Exception as e:
            print(f"❌ Error uploading {local_path}: {e}")
            return False
    
    def upload_processed_files(self, video_path, audio_path=None, transcript_path=None):
        """Upload processed video, audio, and transcript files"""
        print(f"🌐 Uploading processed files to R2...")
        print(f"📂 Upload directory: {UPLOAD_DIR}")
        
        upload_success = True
        
        # Upload video file
        if video_path and video_path.exists():
            video_remote_key = f"{UPLOAD_DIR}/final_video_{USER_ID}.webm"
            if not self.upload_file(video_path, video_remote_key):
                upload_success = False
        
        # Upload audio file if it exists
        if audio_path and audio_path.exists():
            audio_remote_key = f"{UPLOAD_DIR}/final_audio_{USER_ID}.webm"
            if not self.upload_file(audio_path, audio_remote_key):
                upload_success = False
        
        # Upload transcript file if it exists
        if transcript_path and transcript_path.exists():
            transcript_remote_key = f"{UPLOAD_DIR}/transcript_{USER_ID}.json"
            if not self.upload_file(transcript_path, transcript_remote_key):
                upload_success = False
        
        return upload_success

class VideoProcessor:
    def __init__(self, video_chunks_dir, audio_chunks_dir, video_output_dir, audio_output_dir):
        self.video_chunks_dir = Path(video_chunks_dir)
        self.audio_chunks_dir = Path(audio_chunks_dir)
        self.video_output_dir = Path(video_output_dir)
        self.audio_output_dir = Path(audio_output_dir)
        
        # Create output directories
        self.video_output_dir.mkdir(parents=True, exist_ok=True)
        self.audio_output_dir.mkdir(parents=True, exist_ok=True)
        
    def run_ffmpeg(self, command, description="FFmpeg operation"):
        """Execute FFmpeg command with proper error handling"""
        print(f"[ffmpeg] {description}")
        print(f"[ffmpeg] Running: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            print(f"[ffmpeg] Error: {e}")
            if e.stderr:
                print(f"[ffmpeg] stderr: {e.stderr}")
            return False, e.stderr
    
    def find_chunk_sequences(self):
        """Find video and audio chunk sequences"""
        video_chunks = []
        audio_chunks = []
        
        # Find all video chunks in video directory
        for i in range(1000):  # reasonable upper bound
            video_file = self.video_chunks_dir / f"video_{i}.webm"
            if video_file.exists():
                video_chunks.append((i, video_file))
        
        # Find all audio chunks in audio directory
        for i in range(1000):  # reasonable upper bound
            audio_file = self.audio_chunks_dir / f"audio_{i}.webm"
            if audio_file.exists():
                audio_chunks.append((i, audio_file))
        
        # Sort by index
        video_chunks.sort(key=lambda x: x[0])
        audio_chunks.sort(key=lambda x: x[0])
        
        print(f"📊 Found {len(video_chunks)} video chunks and {len(audio_chunks)} audio chunks")
        
        return video_chunks, audio_chunks
    
    def concatenate_raw_chunks(self, chunks, output_path, chunk_type="video"):
        """Concatenate raw WebM chunks using binary concatenation first, then fix with FFmpeg"""
        if not chunks:
            return False
            
        print(f"🔗 Concatenating {len(chunks)} {chunk_type} chunks...")
        
        # First, try binary concatenation to a temporary file
        temp_concat_path = output_path.with_suffix('.temp.webm')
        
        try:
            with open(temp_concat_path, 'wb') as outfile:
                for i, (index, chunk_path) in enumerate(chunks):
                    print(f"   Adding {chunk_type}_{index}.webm")
                    with open(chunk_path, 'rb') as infile:
                        outfile.write(infile.read())
            
            print(f"📦 Raw concatenation complete, fixing with FFmpeg...")
            
            # Now use FFmpeg to fix the concatenated file
            command = [
                "ffmpeg",
                "-y",
                "-fflags", "+genpts",  # Generate PTS for frames
                "-i", str(temp_concat_path),
                "-c", "copy",  # Copy without re-encoding
                "-avoid_negative_ts", "make_zero",
                str(output_path)
            ]
            
            success, output = self.run_ffmpeg(
                command,
                f"Fixing concatenated {chunk_type} file"
            )
            
            # Clean up temp file
            if temp_concat_path.exists():
                temp_concat_path.unlink()
            
            return success
            
        except Exception as e:
            print(f"❌ Error during raw concatenation: {e}")
            if temp_concat_path.exists():
                temp_concat_path.unlink()
            return False
    
    def mux_video_audio(self, video_path, audio_path, output_path):
        """Mux video and audio streams together"""
        command = [
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "copy",
            "-shortest",  # End when the shorter stream ends
            "-avoid_negative_ts", "make_zero",
            str(output_path)
        ]
        
        success, output = self.run_ffmpeg(
            command,
            "Muxing video and audio streams"
        )
        
        return success
    
    def process_chunks(self):
        """Main processing function"""
        print("🔍 Scanning for chunk sequences...")
        
        # Find all chunks
        video_chunks, audio_chunks = self.find_chunk_sequences()
        
        if not video_chunks:
            print("❌ No video chunks found!")
            return None, None
        
        if not audio_chunks:
            print("⚠️  No audio chunks found, will create video-only output")
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            print(f"📁 Using temporary directory: {temp_dir}")
            
            # Step 1: Concatenate video chunks
            print("\n🎬 Processing video chunks...")
            video_concat_path = temp_dir / "video_concatenated.webm"
            
            if not self.concatenate_raw_chunks(video_chunks, video_concat_path, "video"):
                print("❌ Failed to concatenate video chunks!")
                return None, None
            
            # Step 2: Concatenate audio chunks (if they exist)
            audio_concat_path = None
            if audio_chunks:
                print("\n🎵 Processing audio chunks...")
                audio_concat_path = temp_dir / "audio_concatenated.webm"
                
                if not self.concatenate_raw_chunks(audio_chunks, audio_concat_path, "audio"):
                    print("⚠️  Failed to concatenate audio chunks, proceeding with video only")
                    audio_concat_path = None
            
            # Step 3: Generate output filenames with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            final_video_path = self.video_output_dir / f"output_{timestamp}.webm"
            final_audio_path = self.audio_output_dir / f"audio_{timestamp}.webm"
            
            # Step 4: Save audio file to AUD_DIR if available
            saved_audio_path = None
            if audio_concat_path and audio_concat_path.exists():
                print(f"\n🎵 Saving complete audio file to: {final_audio_path}")
                try:
                    shutil.copy2(audio_concat_path, final_audio_path)
                    saved_audio_path = final_audio_path
                    print(f"✅ Audio file saved successfully!")
                except Exception as e:
                    print(f"❌ Failed to save audio file: {e}")
            
            # Step 5: Create final video file
            if audio_concat_path and audio_concat_path.exists():
                print(f"\n🎞️  Muxing video and audio into final output: {final_video_path}")
                
                if self.mux_video_audio(video_concat_path, audio_concat_path, final_video_path):
                    print(f"✅ Success! Final video with audio saved at:")
                    print(f"   {final_video_path}")
                    return final_video_path, saved_audio_path
                else:
                    print("❌ Failed to mux video and audio!")
                    return None, saved_audio_path
            else:
                # Video only output
                print(f"\n🎞️  Creating video-only output: {final_video_path}")
                
                try:
                    shutil.copy2(video_concat_path, final_video_path)
                    print(f"✅ Success! Video-only file saved at:")
                    print(f"   {final_video_path}")
                    return final_video_path, saved_audio_path
                except Exception as e:
                    print(f"❌ Failed to copy video file: {e}")
                    return None, saved_audio_path

class WhisperTranscriber:
    def __init__(self, model_size="base"):
        """
        Initialize Whisper transcriber
        
        Args:
            model_size (str): Whisper model size - tiny, base, small, medium, large
        """
        self.model_size = model_size
        self.model = None
        print(f"🎤 Whisper Transcriber initialized with {model_size} model")
    
    def load_model(self):
        """Load the Whisper model"""
        if self.model is None:
            print(f"📥 Loading Whisper {self.model_size} model...")
            try:
                self.model = whisper.load_model(self.model_size)
                print(f"✅ Whisper model loaded successfully")
                return True
            except Exception as e:
                print(f"❌ Failed to load Whisper model: {e}")
                return False
        return True
    
    def transcribe_audio(self, audio_path, output_dir):
        """
        Transcribe audio file using Whisper
        
        Args:
            audio_path (Path): Path to audio file
            output_dir (Path): Directory to save transcript
            
        Returns:
            Path: Path to generated transcript file, or None if failed
        """
        if not self.load_model():
            return None
        
        print(f"🎤 Transcribing audio file: {audio_path}")
        
        try:
            # Transcribe the audio
            result = self.model.transcribe(str(audio_path))
            
            # Create output directory if it doesn't exist
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate timestamp for filename
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            transcript_path = output_dir / f"transcript_{timestamp}.json"
            
            # Prepare transcript data
            transcript_data = {
                "meeting_id": MEETING_ID,
                "take": TAKE,
                "user_id": USER_ID,
                "timestamp": timestamp,
                "model_used": self.model_size,
                "language": result.get("language", "unknown"),
                "full_text": result["text"].strip(),
                "segments": []
            }
            
            # Add detailed segments with timestamps
            for segment in result.get("segments", []):
                transcript_data["segments"].append({
                    "id": segment.get("id"),
                    "start": segment.get("start"),
                    "end": segment.get("end"),
                    "text": segment.get("text", "").strip()
                })
            
            # Save transcript to JSON file
            with open(transcript_path, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Transcript generated successfully!")
            print(f"📝 Language detected: {transcript_data['language']}")
            print(f"📊 Segments: {len(transcript_data['segments'])}")
            print(f"📁 Transcript saved: {transcript_path}")
            
            # Show preview of transcription
            preview_text = transcript_data["full_text"][:200]
            if len(transcript_data["full_text"]) > 200:
                preview_text += "..."
            print(f"📖 Preview: {preview_text}")
            
            return transcript_path
            
        except Exception as e:
            print(f"❌ Transcription failed: {e}")
            return None

class VideoPipeline:
    def __init__(self, whisper_model="base"):
        self.r2_manager = CloudflareR2Manager()
        self.transcriber = WhisperTranscriber(whisper_model)
        print(f"🚀 Video Processing Pipeline Initialized")
        print(f"📋 Meeting ID: {MEETING_ID}")
        print(f"📋 Take: {TAKE}")
        print(f"📋 User ID: {USER_ID}")
        print(f"🎤 Whisper Model: {whisper_model}")
    
    def setup_directories(self):
        """Create necessary local directories"""
        print(f"📁 Setting up local directories...")
        
        directories = [
            LOCAL_DIR,
            os.path.join(LOCAL_DIR, "video"),
            os.path.join(LOCAL_DIR, "audio"),
            OUTPUT_DIR,
            os.path.join(OUTPUT_DIR, "video"),
            os.path.join(OUTPUT_DIR, "audio"),
            os.path.join(OUTPUT_DIR, "transcripts")
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            print(f"   Created: {directory}")
    
    def check_ffmpeg(self):
        """Check if FFmpeg is available"""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            print("✅ FFmpeg found and ready")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ FFmpeg not found! Please install FFmpeg and ensure it's in your PATH")
            return False
    
    def process_chunks(self):
        """Process downloaded chunks into video/audio files"""
        print(f"🎬 Processing chunks into final video/audio...")
        
        video_chunks_dir = os.path.join(LOCAL_DIR, "video")
        audio_chunks_dir = os.path.join(LOCAL_DIR, "audio")
        video_output_dir = os.path.join(OUTPUT_DIR, "video")
        audio_output_dir = os.path.join(OUTPUT_DIR, "audio")
        
        processor = VideoProcessor(video_chunks_dir, audio_chunks_dir, video_output_dir, audio_output_dir)
        return processor.process_chunks()
    
    def transcribe_audio(self, audio_path):
        """Generate transcript from audio file"""
        if not audio_path or not audio_path.exists():
            print("⚠️  No audio file available for transcription")
            return None
        
        print(f"🎤 Starting audio transcription...")
        transcript_output_dir = os.path.join(OUTPUT_DIR, "transcripts")
        return self.transcriber.transcribe_audio(audio_path, transcript_output_dir)
    
    def cleanup_local_files(self):
        """Clean up temporary local files"""
        print(f"🧹 Cleaning up local files...")
        try:
            if os.path.exists(LOCAL_DIR):
                shutil.rmtree(LOCAL_DIR)
                print(f"   Removed: {LOCAL_DIR}")
            
            if os.path.exists(OUTPUT_DIR):
                shutil.rmtree(OUTPUT_DIR)
                print(f"   Removed: {OUTPUT_DIR}")
        except Exception as e:
            print(f"⚠️  Warning: Could not clean up some files: {e}")
    
    def run(self, cleanup=True, skip_transcription=False):
        """Run the complete pipeline"""
        start_time = datetime.now()
        print(f"🚀 Starting video processing pipeline at {start_time}")
        print("=" * 60)
        
        try:
            # Step 1: Setup directories
            print(f"\n📁 Step 1: Setting up directories")
            self.setup_directories()
            
            # Step 2: Check FFmpeg
            print(f"\n🔧 Step 2: Checking FFmpeg availability")
            if not self.check_ffmpeg():
                return False
            
            # Step 3: Download chunks
            print(f"\n📥 Step 3: Downloading chunks from R2")
            if not self.r2_manager.download_chunks():
                return False
            
            # Step 4: Process chunks
            print(f"\n🎬 Step 4: Processing chunks")
            video_path, audio_path = self.process_chunks()
            
            if not video_path:
                print("❌ Failed to process chunks!")
                return False
            
            # Step 5: Generate transcript (if audio available and not skipped)
            transcript_path = None
            if not skip_transcription and audio_path:
                print(f"\n🎤 Step 5: Generating transcript")
                transcript_path = self.transcribe_audio(audio_path)
                
                if transcript_path:
                    print("✅ Transcript generated successfully!")
                else:
                    print("⚠️  Transcript generation failed, continuing without transcript")
            elif skip_transcription:
                print(f"\n⏭️  Step 5: Skipping transcription (--no-transcript flag)")
            else:
                print(f"\n⏭️  Step 5: Skipping transcription (no audio file)")
            
            # Step 6: Upload processed files
            print(f"\n📤 Step 6: Uploading processed files")
            if not self.r2_manager.upload_processed_files(video_path, audio_path, transcript_path):
                print("❌ Failed to upload some files!")
                return False
            
            print(f"\n🎉 Pipeline completed successfully!")
            print(f"✅ Video file processed and uploaded")
            if audio_path:
                print(f"✅ Audio file processed and uploaded")
            if transcript_path:
                print(f"✅ Transcript generated and uploaded")
            
            return True
            
        except Exception as e:
            print(f"💥 Pipeline failed with error: {e}")
            return False
        
        finally:
            # Step 7: Cleanup (optional)
            if cleanup:
                print(f"\n🧹 Step 7: Cleaning up local files")
                self.cleanup_local_files()
            
            end_time = datetime.now()
            duration = end_time - start_time
            print(f"\n⏱️  Total pipeline time: {duration}")
            print("=" * 60)

def main():
    """Main entry point"""
    print("🎥 Video Processing Pipeline with Whisper Transcription")
    print("=" * 60)
    
    # Parse command line arguments
    cleanup = True
    skip_transcription = False
    whisper_model = "base"
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--no-cleanup':
            cleanup = False
            print("🗂️  Local files will be preserved after processing")
        elif arg == '--no-transcript':
            skip_transcription = True
            print("⏭️  Transcription will be skipped")
        elif arg == '--whisper-model':
            if i + 1 < len(sys.argv):
                whisper_model = sys.argv[i + 1]
                i += 1  # Skip next argument as it's the model name
                print(f"🎤 Using Whisper model: {whisper_model}")
            else:
                print("❌ --whisper-model requires a model name (tiny, base, small, medium, large)")
                sys.exit(1)
        elif arg == '--help':
            print("""
Usage: python pipeline.py [options]

Options:
    --no-cleanup        Preserve local files after processing
    --no-transcript     Skip audio transcription
    --whisper-model     Specify Whisper model (tiny, base, small, medium, large)
                       Default: base
    --help             Show this help message

Examples:
    python pipeline.py                                    # Default: process with cleanup and base model
    python pipeline.py --no-cleanup                      # Keep local files
    python pipeline.py --whisper-model large             # Use large Whisper model
    python pipeline.py --no-transcript                   # Skip transcription
    python pipeline.py --whisper-model medium --no-cleanup # Custom model + keep files
            """)
            sys.exit(0)
        else:
            print(f"❌ Unknown argument: {arg}")
            print("Use --help for usage information")
            sys.exit(1)
        i += 1
    
    # Validate Whisper model
    valid_models = ["tiny", "base", "small", "medium", "large"]
    if whisper_model not in valid_models:
        print(f"❌ Invalid Whisper model: {whisper_model}")
        print(f"Valid models: {', '.join(valid_models)}")
        sys.exit(1)
    
    # Run the pipeline
    pipeline = VideoPipeline(whisper_model=whisper_model)
    success = pipeline.run(cleanup=cleanup, skip_transcription=skip_transcription)
    
    if success:
        print("🎊 All operations completed successfully!")
        sys.exit(0)
    else:
        print("💥 Pipeline failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()