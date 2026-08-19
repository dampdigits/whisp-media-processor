import threading
import requests
from flask import request, jsonify
from app import app
from app.driver import set_config
from app.worker import VideoPipeline

@app.route("/submit", methods=["POST"])
def submit_data():
    """ Get Meeting ID, Take, User ID and start video processing """
    try:
        # Get JSON data from the POST request
        data = request.get_json()

        # If the data is not in JSON format
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # Get required parameters
        MEETING_ID = data.get('meeting_id')
        TAKE = data.get('take')
        USER_ID = data.get('user_id')

        if not (MEETING_ID and TAKE and USER_ID):
            return jsonify({"error": "Missing required tokens: 'meeting_id', 'take', 'user_id'"}), 400

        # Set configuration variables
        config = set_config(MEETING_ID, TAKE, USER_ID)
        
        print("🚀 Starting video processing pipeline for:")
        print(f"   Meeting ID: {MEETING_ID}")
        print(f"   Take: {TAKE}")
        print(f"   User ID: {USER_ID}")
        print(f"   Remote Directory: {config['REMOTE_DIR']}")
        print(f"   Local Directory: {config['LOCAL_DIR']}")
        print(f"   Output Directory: {config['OUTPUT_DIR']}")
        print(f"   Upload Directory: {config['UPLOAD_DIR']}")

        # Get optional parameters
        whisper_model = data.get('whisper_model', 'base')
        cleanup = data.get('cleanup', True)
        skip_transcription = data.get('skip_transcription', False)

        # Validate whisper model
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if whisper_model not in valid_models:
            return jsonify({
                "error": f"Invalid whisper model: {whisper_model}. Valid models: {', '.join(valid_models)}"
            }), 400

        # Start the video processing pipeline in a separate thread
        def run_pipeline():
            try:
                pipeline = VideoPipeline(
                    meeting_id=MEETING_ID,
                    take=TAKE,
                    user_id=USER_ID,
                    remote_dir=config['REMOTE_DIR'],
                    local_dir=config['LOCAL_DIR'],
                    output_dir=config['OUTPUT_DIR'],
                    upload_dir=config['UPLOAD_DIR'],
                    whisper_model=whisper_model
                )
                success = pipeline.run(cleanup=cleanup, skip_transcription=skip_transcription)
                
                if success:
                    print(f"✅ Pipeline completed successfully for {MEETING_ID}/{TAKE}/{USER_ID}")
                    
                    # Prepare the upload URLs for the completed files
                    base_r2_url = f"https://{pipeline.r2_manager.BUCKET_NAME}.{pipeline.r2_manager.ACCOUNT_ID}.r2.cloudflarestorage.com"
                    upload_urls = {
                        "video_url": f"{base_r2_url}/{config['UPLOAD_DIR']}/final_video_{USER_ID}.mp4",
                        "subtitle_url": f"{base_r2_url}/{config['UPLOAD_DIR']}/subtitle_{USER_ID}.srt"
                    }
                    
                    # Add audio URL if audio was processed
                    if not skip_transcription:
                        upload_urls["audio_url"] = f"{base_r2_url}/{config['UPLOAD_DIR']}/final_audio_{USER_ID}.wav"
                    
                    # Send completion notification with upload URLs
                    try:
                        completion_url = f'https://api.compilo.xyz/processing-finished/{MEETING_ID}/{TAKE}/{USER_ID}'
                        response = requests.post(
                            completion_url,
                            json={
                                "status": "completed",
                                "meeting_id": MEETING_ID,
                                "take": TAKE,
                                "user_id": USER_ID,
                                "upload_urls": upload_urls,
                                "processing_options": {
                                    "whisper_model": whisper_model,
                                    "cleanup": cleanup,
                                    "skip_transcription": skip_transcription
                                }
                            },
                            headers={'Content-Type': 'application/json'},
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            print(f"✅ Completion notification sent successfully to {completion_url}")
                            print(f"📤 Uploaded files URLs:")
                            for key, url in upload_urls.items():
                                print(f"   {key}: {url}")
                        else:
                            print(f"⚠️  Completion notification failed: {response.status_code} - {response.text}")
                            
                    except requests.exceptions.RequestException as e:
                        print(f"❌ Failed to send completion notification: {e}")
                        print("📤 Upload URLs (notification failed):")
                        for key, url in upload_urls.items():
                            print(f"   {key}: {url}")
                    
                else:
                    print(f"❌ Pipeline failed for {MEETING_ID}/{TAKE}/{USER_ID}")
                    
                    # Send failure notification
                    try:
                        completion_url = f'https://api.compilo.xyz/processing-finished/{MEETING_ID}/{TAKE}/{USER_ID}'
                        response = requests.post(
                            completion_url,
                            json={
                                "status": "failed",
                                "meeting_id": MEETING_ID,
                                "take": TAKE,
                                "user_id": USER_ID,
                                "error": "Pipeline processing failed"
                            },
                            headers={'Content-Type': 'application/json'},
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            print(f"✅ Failure notification sent successfully")
                        else:
                            print(f"⚠️  Failure notification failed: {response.status_code}")
                            
                    except requests.exceptions.RequestException as e:
                        print(f"❌ Failed to send failure notification: {e}")
                    
            except Exception as pipeline_error:
                print(f"💥 Pipeline exception for {MEETING_ID}/{TAKE}/{USER_ID}: {pipeline_error}")
                
                # Send exception notification
                try:
                    completion_url = f'https://api.compilo.xyz/processing-finished/{MEETING_ID}/{TAKE}/{USER_ID}'
                    response = requests.post(
                        completion_url,
                        json={
                            "status": "error",
                            "meeting_id": MEETING_ID,
                            "take": TAKE,
                            "user_id": USER_ID,
                            "error": str(pipeline_error)
                        },
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        print(f"✅ Exception notification sent successfully")
                    else:
                        print(f"⚠️  Exception notification failed: {response.status_code}")
                        
                except requests.exceptions.RequestException as e:
                    print(f"❌ Failed to send exception notification: {e}")

        # Start pipeline in background thread
        pipeline_thread = threading.Thread(target=run_pipeline)
        pipeline_thread.daemon = True
        pipeline_thread.start()

        # Return immediate response
        return jsonify({
            "status": "success",
            "message": "Video processing pipeline started",
            "meeting_id": MEETING_ID,
            "take": TAKE,
            "user_id": USER_ID,
            "config": config,
            "options": {
                "whisper_model": whisper_model,
                "cleanup": cleanup,
                "skip_transcription": skip_transcription
            }
        }), 200

    except Exception as api_error:
        print(f"❌ Error in submit_data: {api_error}")
        return jsonify({"error": str(api_error)}), 500

@app.route("/status", methods=["GET"])
def get_status():
    """ Get processing status """
    return jsonify({
        "status": "running",
        "message": "Video processing service is running"
    }), 200