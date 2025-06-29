#!/usr/bin/env python3
"""
Configuration driver for video processing pipeline
These variables will be set dynamically from the Flask API
"""

# Default values - will be overridden by API calls
MEETING_ID = None
TAKE = None
USER_ID = None
PREFIX = "recordings"
DIR = None
REMOTE_DIR = None
LOCAL_DIR = None
OUTPUT_DIR = None
UPLOAD_DIR = None

def set_config(meeting_id, take, user_id):
    """
    Set configuration variables dynamically
    
    Args:
        meeting_id (str): Meeting identifier
        take (str): Take number
        user_id (str): User identifier
    """
    # Use globals to update module-level variables
    global MEETING_ID, TAKE, USER_ID, PREFIX, DIR, REMOTE_DIR, LOCAL_DIR, OUTPUT_DIR, UPLOAD_DIR
    
    MEETING_ID = meeting_id
    TAKE = take
    USER_ID = user_id
    
    PREFIX = "recordings"
    DIR = '/'.join([MEETING_ID, TAKE, USER_ID])
    
    REMOTE_DIR = PREFIX + "/" + DIR
    LOCAL_DIR = "../chunks/" + DIR
    OUTPUT_DIR = "../recordings/" + DIR
    UPLOAD_DIR = PREFIX + "/" + '/'.join([MEETING_ID, TAKE])
    
    return {
        "MEETING_ID": MEETING_ID,
        "TAKE": TAKE,
        "USER_ID": USER_ID,
        "PREFIX": PREFIX,
        "DIR": DIR,
        "REMOTE_DIR": REMOTE_DIR,
        "LOCAL_DIR": LOCAL_DIR,
        "OUTPUT_DIR": OUTPUT_DIR,
        "UPLOAD_DIR": UPLOAD_DIR
    }