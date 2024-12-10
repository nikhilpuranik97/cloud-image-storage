import os
import hashlib
from Crypto.Cipher import Blowfish
from Crypto.Util.Padding import pad
import cv2
import pywt
import numpy as np
from PIL import Image, PngImagePlugin
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr
import boto3

BUCKET_NAME = "my-encrypted-images-bucket"

# Create directories if they don't exist
if not os.path.exists("compressed_images"):
    os.makedirs("compressed_images")
if not os.path.exists("metadata_images"):
    os.makedirs("metadata_images")

# Upload to S3
def upload_to_s3(file_path, bucket_name, s3_key):
    s3_client = boto3.client("s3")
    s3_client.upload_file(file_path, bucket_name, s3_key)
    return f"s3://{bucket_name}/{s3_key}"

# Evaluate Compression Performance
def evaluate_compression(original_image, compressed_path):
    original = cv2.imread(original_image)
    compressed = cv2.imread(compressed_path)
    compressed_resized = cv2.resize(compressed, (original.shape[1], original.shape[0]))

    psnr_value = psnr(original, compressed_resized, data_range=255)
    ssim_value = ssim(original, compressed_resized, multichannel=True, channel_axis=-1)
    compression_ratio = os.path.getsize(original_image) / os.path.getsize(compressed_path)
    return {
        "PSNR": psnr_value,
        "SSIM": ssim_value,
        "Compression Ratio": compression_ratio
    }

# Compress Image
def compress_image(image_path, quality=70):
    # Extract file name and extension
    file_name, file_extension = os.path.splitext(os.path.basename(image_path))
    
    image = cv2.imread(image_path)
    channels = cv2.split(image)
    compressed_channels = []

    for channel in channels:
        coeffs2 = pywt.dwt2(channel, 'db2')
        LL, (LH, HL, HH) = coeffs2
        threshold = 15
        LH = np.where(np.abs(LH) > threshold, LH, 0)
        HL = np.where(np.abs(HL) > threshold, HL, 0)
        HH = np.where(np.abs(HH) > threshold, HH, 0)
        compressed_channel = pywt.idwt2((LL, (LH, HL, HH)), 'db2')
        compressed_channels.append(compressed_channel)

    compressed_image = cv2.merge(compressed_channels)
    compressed_image = np.clip(compressed_image, 0, 255).astype(np.uint8)

    compressed_path = os.path.join("compressed_images", f"{file_name}.compressed{file_extension}")
    if compressed_path.endswith(".jpg"):
        cv2.imwrite(compressed_path, compressed_image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    else:
        cv2.imwrite(compressed_path, compressed_image)
    return compressed_path

# Encrypt Image
def encrypt_image(file_path, password):
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), b'salt', 100000, dklen=32)
    cipher = Blowfish.new(key, Blowfish.MODE_CBC)
    iv = cipher.iv
    with open(file_path, 'rb') as file:
        file_data = file.read()
    padded_data = pad(file_data, Blowfish.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    encrypted_path = "encrypted_image.enc"
    with open(encrypted_path, "wb") as enc_file:
        enc_file.write(iv + encrypted_data)
    return encrypted_path, hashlib.sha256(encrypted_data).hexdigest()

# Embed Hash in Metadata
def embed_hash_in_metadata(image_path, hash_string, compression_settings, retry=False):
    # Extract file name and extension
    file_name, file_extension = os.path.splitext(os.path.basename(image_path))

    metadata_path = os.path.join("metadata_images", f"{file_name}.metadata-embedded{file_extension}")
    try:
        image = Image.open(image_path)
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Hash", hash_string[:8])  # Truncate hash for metadata

        if image.format == "JPEG":
            quality = compression_settings.get("jpeg_quality", 80 if not retry else 60)
            image.save(metadata_path, format="JPEG", quality=quality)
        elif image.format == "PNG":
            compress_level = compression_settings.get("png_compression_level", 6 if not retry else 9)
            image.save(metadata_path, format="PNG", pnginfo=metadata, compress_level=compress_level)
        else:
            image.save(metadata_path, format=image.format)
        return metadata_path
    except Exception as e:
        print(f"Error embedding hash in metadata for {image_path}: {e}")
        return None

# Compare File Sizes
def compare_file_sizes(original_path, metadata_path):
    original_size = os.path.getsize(original_path)
    metadata_size = os.path.getsize(metadata_path)
    size_difference = metadata_size - original_size
    percentage_difference = (size_difference / original_size) * 100
    return {
        "Original Size": original_size,
        "Metadata Size": metadata_size,
        "Difference (Bytes)": size_difference,
        "Difference (%)": percentage_difference
    }
