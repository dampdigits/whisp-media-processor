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


class CloudflareR2Manager:
    def __init__(self, remote_dir, local_dir, upload_dir, user_id):
        # Load environment variables
        load_dotenv()
        
        # Store configuration
        self.remote_dir = remote_dir
        self.local_dir = local_dir
        self.upload_dir = upload_dir
        self.user_id = user_id
        
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
        print(f"📂 Remote directory: {self.remote_dir}")
        print(f"📂 Local directory: {self.local_dir}")
        
        try:
            response = self.s3.list_objects_v2(Bucket=self.BUCKET_NAME, Prefix=self.remote_dir)
            print(response)
            
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
                
                DOWNLOAD_DIR = self.local_dir + DOWNLOAD_FOLDER
                
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
    
    def upload_processed_files(self, video_path, audio_path=None, transcript_paths=None):
        """Upload processed video, audio, and transcript files"""
        print(f"🌐 Uploading processed files to R2...")
        print(f"📂 Upload directory: {self.upload_dir}")
        
        upload_success = True
        
        # Upload video file
        if video_path and video_path.exists():
            video_remote_key = f"{self.upload_dir}/final_video_{self.user_id}.mp4"  # Changed to .mp4
            if not self.upload_file(video_path, video_remote_key):
                upload_success = False
        
        # Upload audio file if it exists
        if audio_path and audio_path.exists():
            # Get the file extension from the source file
            audio_ext = audio_path.suffix  # This will include the dot (.wav)
            audio_remote_key = f"{self.upload_dir}/final_audio_{self.user_id}{audio_ext}"
            if not self.upload_file(audio_path, audio_remote_key):
                upload_success = False
        
        # Upload transcript files if they exist
        if transcript_paths:
            json_path, srt_path = transcript_paths if isinstance(transcript_paths, tuple) else (transcript_paths, None)
            
            # Upload JSON transcript
            # if json_path and Path(json_path).exists():
            #     json_remote_key = f"{self.upload_dir}/transcript_{self.user_id}.json"
            #     if not self.upload_file(json_path, json_remote_key):
            #         upload_success = False
            
            # Upload SRT transcript
            if srt_path and Path(srt_path).exists():
                srt_remote_key = f"{self.upload_dir}/subtitle_{self.user_id}.srt"
                if not self.upload_file(srt_path, srt_remote_key):
                    upload_success = False
        
        return upload_success

class VideoProcessor:
    def __init__(self, video_chunks_dir, audio_chunks_dir, video_output_dir, audio_output_dir, transcript_output_dir=None):
        self.video_chunks_dir = Path(video_chunks_dir)
        self.audio_chunks_dir = Path(audio_chunks_dir)
        self.video_output_dir = Path(video_output_dir)
        self.audio_output_dir = Path(audio_output_dir)
        self.transcript_output_dir = Path(transcript_output_dir) if transcript_output_dir else None
        
        # Create output directories
        self.video_output_dir.mkdir(parents=True, exist_ok=True)
        self.audio_output_dir.mkdir(parents=True, exist_ok=True)
        if self.transcript_output_dir:
            self.transcript_output_dir.mkdir(parents=True, exist_ok=True)
        
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
    
    def mux_video_audio_with_captions(self, video_path, audio_path, srt_path, output_path):
        """Mux video and audio streams together with soft captions into MP4"""
        # First add all input files
        command = ["ffmpeg", "-y"]
        
        # Add video input
        command.extend(["-i", str(video_path)])
        
        # Add audio input if available
        if audio_path:
            command.extend(["-i", str(audio_path)])
        
        # Add subtitle input if available
        if srt_path and Path(srt_path).exists():
            command.extend(["-i", str(srt_path)])
        
        # Now add output options
        # Video codec - use h264 for better compatibility
        command.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23"])
        
        # Audio codec if audio is available
        if audio_path:
            command.extend(["-c:a", "aac", "-b:a", "128k"])
        
        # Subtitle codec if available
        if srt_path and Path(srt_path).exists():
            command.extend(["-c:s", "mov_text", "-metadata:s:s:0", "language=eng"])
        
        # Other options
        command.extend(["-shortest", "-avoid_negative_ts", "make_zero"])
        
        # Output file
        command.append(str(output_path))
        
        success, output = self.run_ffmpeg(
            command,
            "Creating MP4 with video, audio, and soft captions"
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
            final_video_path = self.video_output_dir / f"output_{timestamp}.mp4"  # Changed to MP4
            final_audio_path = self.audio_output_dir / f"audio_{timestamp}.wav"  # Use WAV format
            
            # Step 4: Create final video file first
            saved_audio_path = None
            if audio_concat_path and audio_concat_path.exists():
                print(f"\n🎞️  Muxing video and audio into final output: {final_video_path}")
                
                # Convert WebM to WAV for audio file
                print(f"\n🎵 Converting audio to WAV format: {final_audio_path}")
                try:
                    # Convert WebM to WAV using FFmpeg
                    command = [
                        "ffmpeg",
                        "-y",
                        "-i", str(audio_concat_path),
                        "-acodec", "pcm_s16le",  # Standard WAV format
                        "-ar", "44100",          # Sample rate
                        str(final_audio_path)
                    ]
                    
                    success, output = self.run_ffmpeg(
                        command,
                        "Converting audio to WAV format"
                    )
                    
                    if success:
                        saved_audio_path = final_audio_path
                        print(f"✅ Audio file converted and saved as WAV successfully!")
                    else:
                        print(f"❌ Failed to convert audio to WAV format")
                except Exception as e:
                    print(f"❌ Failed to save audio as WAV: {e}")
                
                # For video, create MP4 directly (without soft captions here)
                command = [
                    "ffmpeg",
                    "-y",
                    "-i", str(video_concat_path),
                    "-i", str(audio_concat_path),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-shortest",
                    "-avoid_negative_ts", "make_zero",
                    str(final_video_path)
                ]
                
                success, _ = self.run_ffmpeg(command, "Creating MP4 video with audio")
                
                if success:
                    print(f"✅ Success! Final video with audio saved at:")
                    print(f"   {final_video_path}")
                    return final_video_path, saved_audio_path
                else:
                    print("❌ Failed to mux video and audio!")
                    return None, None
            else:
                # Video only output as MP4
                print(f"\n🎞️  Creating video-only MP4 output: {final_video_path}")
                
                command = [
                    "ffmpeg",
                    "-y",
                    "-i", str(video_concat_path),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                    str(final_video_path)
                ]
                
                success, _ = self.run_ffmpeg(command, "Creating MP4 video (no audio)")
                
                if success:
                    print(f"✅ Success! Video-only MP4 file saved at:")
                    print(f"   {final_video_path}")
                    return final_video_path, None
                else:
                    print(f"❌ Failed to create MP4 video file")
                    return None, None
                
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
    
    def format_timestamp(self, seconds):
        """
        Convert seconds to SRT timestamp format (HH:MM:SS,mmm)
        """
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        seconds = seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
    
    def convert_to_srt(self, result):
        """
        Convert Whisper result to SRT format
        
        Args:
            result: Whisper transcription result
            
        Returns:
            str: SRT formatted string
        """
        srt_content = ""
        
        for i, segment in enumerate(result.get("segments", []), 1):
            start_time = self.format_timestamp(segment.get("start", 0))
            end_time = self.format_timestamp(segment.get("end", 0))
            text = segment.get("text", "").strip()
            
            srt_entry = f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
            srt_content += srt_entry
            
        return srt_content
    
    def transcribe_audio(self, audio_path, output_dir, meeting_id, take, user_id):
        """
        Transcribe audio file using Whisper
        
        Args:
            audio_path (Path): Path to audio file
            output_dir (Path): Directory to save transcript
            meeting_id (str): Meeting ID for metadata
            take (str): Take number for metadata
            user_id (str): User ID for metadata
            
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
            json_path = output_dir / f"transcript_{timestamp}.json"
            srt_path = output_dir / f"transcript_{timestamp}.srt"
            
            # Prepare transcript data (JSON)
            transcript_data = {
                "meeting_id": meeting_id,
                "take": take,
                "user_id": user_id,
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
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)
            
            # Convert to SRT and save
            srt_content = self.convert_to_srt(result)
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            print(f"✅ Transcript generated successfully!")
            print(f"📝 Language detected: {transcript_data['language']}")
            print(f"📊 Segments: {len(transcript_data['segments'])}")
            print(f"📁 JSON transcript saved: {json_path}")
            print(f"📁 SRT subtitle saved: {srt_path}")
            
            # Show preview of transcription
            preview_text = transcript_data["full_text"][:200]
            if len(transcript_data["full_text"]) > 200:
                preview_text += "..."
            print(f"📖 Preview: {preview_text}")
            
            # Return both paths as a tuple - for backward compatibility, keep the primary one first
            return json_path, srt_path
            
        except Exception as e:
            print(f"❌ Transcription failed: {e}")
            return None

class VideoPipeline:
    def __init__(self, meeting_id, take, user_id, remote_dir, local_dir, output_dir, upload_dir, whisper_model="base"):
        self.meeting_id = meeting_id
        self.take = take
        self.user_id = user_id
        self.remote_dir = remote_dir
        self.local_dir = local_dir
        self.output_dir = output_dir
        self.upload_dir = upload_dir
        
        self.r2_manager = CloudflareR2Manager(remote_dir, local_dir, upload_dir, user_id)
        self.transcriber = WhisperTranscriber(whisper_model)
        print(f"🚀 Video Processing Pipeline Initialized")
        print(f"📋 Meeting ID: {self.meeting_id}")
        print(f"📋 Take: {self.take}")
        print(f"📋 User ID: {self.user_id}")
        print(f"🎤 Whisper Model: {whisper_model}")
    
    def setup_directories(self):
        """Create necessary local directories"""
        print(f"📁 Setting up local directories...")
        
        directories = [
            self.local_dir,
            os.path.join(self.local_dir, "video"),
            os.path.join(self.local_dir, "audio"),
            self.output_dir,
            os.path.join(self.output_dir, "video"),
            os.path.join(self.output_dir, "audio"),
            os.path.join(self.output_dir, "transcripts")
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
        
        video_chunks_dir = os.path.join(self.local_dir, "video")
        audio_chunks_dir = os.path.join(self.local_dir, "audio")
        video_output_dir = os.path.join(self.output_dir, "video")
        audio_output_dir = os.path.join(self.output_dir, "audio")
        
        processor = VideoProcessor(video_chunks_dir, audio_chunks_dir, video_output_dir, audio_output_dir)
        return processor.process_chunks()
    
    def transcribe_audio(self, audio_path):
        """Generate transcript from audio file"""
        if not audio_path or not audio_path.exists():
            print("⚠️  No audio file available for transcription")
            return None, None
        
        print(f"🎤 Starting audio transcription...")
        transcript_output_dir = os.path.join(self.output_dir, "transcripts")
        return self.transcriber.transcribe_audio(audio_path, transcript_output_dir, self.meeting_id, self.take, self.user_id)
    
    def cleanup_local_files(self):
        """Clean up temporary local files"""
        print(f"🧹 Cleaning up local files...")
        try:
            if os.path.exists(self.local_dir):
                shutil.rmtree(self.local_dir)
                print(f"   Removed: {self.local_dir}")
            
            if os.path.exists(self.output_dir):
                shutil.rmtree(self.output_dir)
                print(f"   Removed: {self.output_dir}")
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
            
            # Step 4: Process video/audio chunks into intermediate files
            print(f"\n🎬 Step 4: Processing chunks into intermediate files")
            video_chunks_dir = os.path.join(self.local_dir, "video")
            audio_chunks_dir = os.path.join(self.local_dir, "audio")
            video_output_dir = os.path.join(self.output_dir, "video")
            audio_output_dir = os.path.join(self.output_dir, "audio")
            transcript_output_dir = os.path.join(self.output_dir, "transcripts")
            
            processor = VideoProcessor(
                video_chunks_dir, 
                audio_chunks_dir, 
                video_output_dir, 
                audio_output_dir,
                transcript_output_dir
            )
            
            # First just concatenate to get our intermediate files
            video_chunks, audio_chunks = processor.find_chunk_sequences()
            
            if not video_chunks:
                print("❌ No video chunks found!")
                return False
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                video_concat_path = temp_dir / "video_concatenated.webm"
                audio_concat_path = None
                
                # Concatenate video chunks
                if not processor.concatenate_raw_chunks(video_chunks, video_concat_path, "video"):
                    print("❌ Failed to process video chunks!")
                    return False
                
                # Concatenate audio chunks if available
                if audio_chunks:
                    audio_concat_path = temp_dir / "audio_concatenated.webm"
                    if not processor.concatenate_raw_chunks(audio_chunks, audio_concat_path, "audio"):
                        print("⚠️ Failed to process audio chunks, continuing with video only")
                        audio_concat_path = None
                
                # Convert audio to WAV for transcription if needed
                audio_wav_path = None
                if audio_concat_path and not skip_transcription:
                    audio_wav_path = temp_dir / "audio_for_transcription.wav"
                    # Convert WebM to WAV using FFmpeg
                    command = [
                        "ffmpeg",
                        "-y",
                        "-i", str(audio_concat_path),
                        "-acodec", "pcm_s16le",
                        "-ar", "44100",
                        str(audio_wav_path)
                    ]
                    
                    success, _ = processor.run_ffmpeg(command, "Converting audio to WAV for transcription")
                    if not success:
                        print("⚠️ Failed to convert audio for transcription, skipping transcription")
                        audio_wav_path = None
                
                # Step 5: Generate transcript
                transcript_paths = None
                srt_path = None
                if not skip_transcription and audio_wav_path and audio_wav_path.exists():
                    print(f"\n🎤 Step 5: Generating transcript")
                    transcript_paths = self.transcriber.transcribe_audio(audio_wav_path, transcript_output_dir, self.meeting_id, self.take, self.user_id)
                    
                    if transcript_paths and len(transcript_paths) > 1:
                        _, srt_path = transcript_paths  # Extract SRT path
                        print(f"✅ SRT transcript generated: {srt_path}")
                    else:
                        print("⚠️ SRT transcript generation failed or not available")
                else:
                    print(f"\n⏭️ Step 5: Skipping transcription (no audio or skipped)")
                
                # Step 6: Generate final outputs
                print(f"\n🎞️ Step 6: Creating final MP4 with soft captions")
                
                # Generate output filenames with timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                final_video_path = Path(video_output_dir) / f"output_{timestamp}.mp4"
                final_audio_path = Path(audio_output_dir) / f"audio_{timestamp}.wav"
                
                # Save audio as WAV if available
                saved_audio_path = None
                if audio_concat_path and audio_concat_path.exists():
                    command = [
                        "ffmpeg",
                        "-y",
                        "-i", str(audio_concat_path),
                        "-acodec", "pcm_s16le",
                        "-ar", "44100",
                        str(final_audio_path)
                    ]
                    
                    success, _ = processor.run_ffmpeg(command, "Saving final audio as WAV")
                    if success:
                        saved_audio_path = final_audio_path
                
                # Create final MP4 with captions
                if processor.mux_video_audio_with_captions(
                    video_concat_path, 
                    audio_concat_path, 
                    srt_path, 
                    final_video_path
                ):
                    print(f"✅ Final MP4 video created successfully: {final_video_path}")
                    video_path = final_video_path
                else:
                    print(f"❌ Failed to create final MP4 video")
                    return False
            
            # Step 7: Upload processed files
            print(f"\n📤 Step 7: Uploading processed files")
            
            # Update the remote keys to use mp4 extension
            if not self.r2_manager.upload_processed_files(video_path, saved_audio_path, transcript_paths):
                print("❌ Failed to upload some files!")
                return False
            
            print(f"\n🎉 Pipeline completed successfully!")
            print(f"✅ MP4 video file processed and uploaded")
            if saved_audio_path:
                print(f"✅ Audio file processed and uploaded")
            if transcript_paths:
                print(f"✅ Transcript generated and uploaded")
            
            return True
            
        except Exception as e:
            print(f"💥 Pipeline failed with error: {e}")
            return False
        
        finally:
            # Step 8: Cleanup (optional)
            if cleanup:
                print(f"\n🧹 Step 8: Cleaning up local files")
                self.cleanup_local_files()
            
            end_time = datetime.now()
            duration = end_time - start_time
            print(f"\n⏱️ Total pipeline time: {duration}")
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