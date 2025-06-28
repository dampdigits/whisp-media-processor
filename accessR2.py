import boto3
import os
from botocore.client import Config
from dotenv import load_dotenv
from driver import REMOTE_DIR, LOCAL_DIR, UPLOAD_DIR

# Load environment variables
load_dotenv()

# Get credentials from environment variables
ACCESS_KEY = os.getenv('S3_ACCESS_KEY_ID')
SECRET_KEY = os.getenv('S3_SECRET_ACCESS_KEY')
ACCOUNT_ID = os.getenv('ACCOUNT_ID')
BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

if not all([ACCESS_KEY, SECRET_KEY, ACCOUNT_ID, BUCKET_NAME]):
    raise ValueError("❌ Couldn't download chunks. Missing required environment variables. Please check your .env file.")

ENDPOINT_URL = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"

# Create S3-compatible client for Cloudflare R2
s3 = boto3.client('s3',
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    endpoint_url=ENDPOINT_URL,
    config=Config(signature_version="s3v4"),
    region_name='auto'
)

# Download chunks
response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=UPLOAD_DIR)
print(f"Download Directory: {LOCAL_DIR}")
for obj in response.get("Contents", []):
    file = obj['Key'].split('/')[-1]
    chunkType = file.split('.')[0].split('_')[0]

    if chunkType == "audio": DOWNLOAD_FOLDER = "/audio"
    else: DOWNLOAD_FOLDER = "/video"
    DOWNLOAD_DIR = LOCAL_DIR + DOWNLOAD_FOLDER

    # Create directory if it doesn't exist
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Full path for the downloaded file
    local_file_path = os.path.join(DOWNLOAD_DIR, file)

    # Download file (will overwrite if exists)
    print(f"Downloading: {obj['Key']} -> {local_file_path}")
    # s3.download_file(BUCKET_NAME, obj['Key'], local_file_path)