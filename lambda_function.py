import boto3
import os
from PIL import Image
from Crypto.Cipher import Blowfish

s3 = boto3.client('s3')

def lambda_handler(event, context):
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']
    
    # Download file to /tmp directory
    local_path = f"/tmp/{os.path.basename(object_key)}"
    s3.download_file(bucket_name, object_key, local_path)

    # Process the image
    processed_file = process_image(local_path)

    # Upload processed file to another S3 bucket
    output_bucket = 'processed-images-bucket'
    output_key = f"processed_{os.path.basename(object_key)}"
    s3.upload_file(processed_file, output_bucket, output_key)
    
    return {
        "statusCode": 200,
        "body": f"File processed and saved to {output_bucket}/{output_key}"
    }

def process_image(file_path):
    compressed_file = compress_image(file_path)
    encrypted_file = encrypt_image(compressed_file)
    return encrypted_file

def compress_image(file_path):
    compressed_file = file_path.replace(".png", "_compressed.png")
    img = Image.open(file_path)
    img.save(compressed_file, optimize=True, quality=50)
    return compressed_file

def encrypt_image(file_path):
    encrypted_file = file_path + ".enc"
    cipher = Blowfish.new(b'secret_key', Blowfish.MODE_ECB)
    with open(file_path, 'rb') as f_in, open(encrypted_file, 'wb') as f_out:
        data = f_in.read()
        f_out.write(cipher.encrypt(data.ljust((len(data) + 7) // 8 * 8)))
    return encrypted_file
