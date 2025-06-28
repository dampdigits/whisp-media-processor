#!/usr/bin/env python3
"""
Complete video processing pipeline:
1. Run driver.py to set up directories
2. Download chunks from Cloudflare R2
3. Process chunks into video/audio files
4. Upload final files back to R2
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

# Import our existing modules
from driver import REMOTE_DIR, LOCAL_DIR, OUTPUT_DIR, UPLOAD_DIR, MEETING_ID, TAKE, USER_ID
from chunksToVideo import VideoProcessor

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
    
    def upload_processed_files(self, video_path, audio_path=None):
        """Upload processed video and audio files"""
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
        
        return upload_success

class VideoPipeline:
    def __init__(self):
        self.r2_manager = CloudflareR2Manager()
        print(f"🚀 Video Processing Pipeline Initialized")
        print(f"📋 Meeting ID: {MEETING_ID}")
        print(f"📋 Take: {TAKE}")
        print(f"📋 User ID: {USER_ID}")
    
    def setup_directories(self):
        """Create necessary local directories"""
        print(f"📁 Setting up local directories...")
        
        directories = [
            LOCAL_DIR,
            os.path.join(LOCAL_DIR, "video"),
            os.path.join(LOCAL_DIR, "audio"),
            OUTPUT_DIR,
            os.path.join(OUTPUT_DIR, "video"),
            os.path.join(OUTPUT_DIR, "audio")
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
    
    def run(self, cleanup=True):
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
            
            # Step 5: Upload processed files
            print(f"\n📤 Step 5: Uploading processed files")
            if not self.r2_manager.upload_processed_files(video_path, audio_path):
                print("❌ Failed to upload some files!")
                return False
            
            print(f"\n🎉 Pipeline completed successfully!")
            print(f"✅ Video file processed and uploaded")
            if audio_path:
                print(f"✅ Audio file processed and uploaded")
            
            return True
            
        except Exception as e:
            print(f"💥 Pipeline failed with error: {e}")
            return False
        
        finally:
            # Step 6: Cleanup (optional)
            if cleanup:
                print(f"\n🧹 Step 6: Cleaning up local files")
                self.cleanup_local_files()
            
            end_time = datetime.now()
            duration = end_time - start_time
            print(f"\n⏱️  Total pipeline time: {duration}")
            print("=" * 60)

def main():
    """Main entry point"""
    print("🎥 Video Processing Pipeline")
    print("=" * 60)
    
    # Parse command line arguments
    cleanup = True
    if len(sys.argv) > 1 and sys.argv[1] == '--no-cleanup':
        cleanup = False
        print("🗂️  Local files will be preserved after processing")
    
    # Run the pipeline
    pipeline = VideoPipeline()
    success = pipeline.run(cleanup=cleanup)
    
    if success:
        print("🎊 All operations completed successfully!")
        sys.exit(0)
    else:
        print("💥 Pipeline failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()