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