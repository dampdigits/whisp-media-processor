MEETING_ID = "xwh5jP"
TAKE = "6"
USER_ID = "601f-18f1-4e6f-87dc"

PREFIX = "recordings"
DIR = '/'.join([MEETING_ID, TAKE, USER_ID])

REMOTE_DIR = PREFIX+"/"+DIR
LOCAL_DIR = "./chunks/"+DIR
OUTPUT_DIR = "./recordings/"+DIR
UPLOAD_DIR = PREFIX+"/"+'/'.join([MEETING_ID, TAKE])

print(f"Remote Directory: {REMOTE_DIR}")