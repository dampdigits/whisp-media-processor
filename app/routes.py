import threading
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
                pipeline = VideoPipeline(whisper_model=whisper_model)
                success = pipeline.run(cleanup=cleanup, skip_transcription=skip_transcription)
                
                if success:
                    print(f"✅ Pipeline completed successfully for {MEETING_ID}/{TAKE}/{USER_ID}")
                else:
                    print(f"❌ Pipeline failed for {MEETING_ID}/{TAKE}/{USER_ID}")
                    
            except Exception as pipeline_error:
                print(f"💥 Pipeline exception for {MEETING_ID}/{TAKE}/{USER_ID}: {pipeline_error}")

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