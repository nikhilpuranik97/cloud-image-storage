import os
import time
import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from compression_encryption import (
    compress_image,
    evaluate_compression,
    encrypt_image,
    embed_hash_in_metadata,
    compare_file_sizes,
    upload_to_s3,
)


def process_image(uploaded_file, password):
    status = []
    results = {}
    timestamps = {}  # to store timestamps for each step
    overall_start = time.time()  # Start the overall timer

    # Step 1: Save the uploaded file temporarily
    try:
        original_file_name = uploaded_file.name
        temp_file_path = original_file_name
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.read())
        status.append("File uploaded successfully.")
        print(f"[INFO] File uploaded: {original_file_name}")
    except Exception as e:
        status.append(f"Error uploading file: {e}")
        print(f"[ERROR] Upload failed for {original_file_name}: {e}")
        return status, None

    # Step 2: Compress the image
    try:
        start = time.time()
        compressed_path = compress_image(temp_file_path)
        compression_metrics = evaluate_compression(temp_file_path, compressed_path)
        timestamps['compression_time'] = time.time() - start  # Record compression time
        status.append("Image compressed successfully.")
        print(f"[INFO] Image compressed: {compressed_path}")
    except Exception as e:
        status.append(f"Error compressing image: {e}")
        print(f"[ERROR] Compression failed for {original_file_name}: {e}")
        return status, None

    # Step 3: Encrypt the image
    try:
        start = time.time()
        encrypted_path, image_hash = encrypt_image(compressed_path, password)
        timestamps['encryption_time'] = time.time() - start  # Record encryption time
        status.append("Image encrypted successfully.")
        print(f"[INFO] Image encrypted: {encrypted_path}")
    except Exception as e:
        status.append(f"Error encrypting image: {e}")
        print(f"[ERROR] Encryption failed for {original_file_name}: {e}")
        return status, None

    # Step 4: Embed metadata in the image
    try:
        start = time.time()
        compression_settings = {"jpeg_quality": 90, "png_compression_level": 9}
        metadata_path = embed_hash_in_metadata(compressed_path, image_hash, compression_settings)
        size_comparison = compare_file_sizes(temp_file_path, metadata_path)
        timestamps['metadata_embedding_time'] = time.time() - start  # Record metadata embedding time
        status.append("Metadata embedded successfully.")
        print(f"[INFO] Metadata embedded: {metadata_path}")
    except Exception as e:
        status.append(f"Error embedding metadata: {e}")
        print(f"[ERROR] Metadata embedding failed for {original_file_name}: {e}")
        return status, None

    # Step 5: Upload compressed and metadata-embedded images to S3
    try:
        compressed_s3_url = upload_to_s3(compressed_path, "my-encrypted-images-bucket", f"compressed_{original_file_name}")
        metadata_s3_url = upload_to_s3(metadata_path, "my-encrypted-images-bucket", f"metadata_{original_file_name}")
        status.append("Images uploaded to S3 successfully.")
        print(f"[INFO] Images uploaded to S3 for {original_file_name}.")
    except Exception as e:
        status.append(f"Error uploading to S3: {e}")
        print(f"[ERROR] S3 upload failed for {original_file_name}: {e}")
        return status, None

    results.update({
        "file_name": original_file_name,
        "compression_metrics": compression_metrics,
        "size_comparison": size_comparison,
        "compressed_s3_url": compressed_s3_url,
        "metadata_s3_url": metadata_s3_url
    })

    # Clean up temporary files
    try:
        os.remove(temp_file_path)
        status.append("Temporary files cleaned up successfully.")
        print(f"[INFO] Temporary files cleaned up for {original_file_name}.")
    except Exception as e:
        status.append(f"Error cleaning up temporary files: {e}")
        print(f"[ERROR] Cleanup failed for {original_file_name}: {e}")

    # Record overall time taken
    timestamps['overall_time'] = time.time() - overall_start

    # Print detailed results in the terminal
    print("\n### Processing Results ###")
    print(f"File Name: {results['file_name']}")
    print("Compression Metrics:")
    print(results["compression_metrics"])
    print("Size Comparison:")
    print(results["size_comparison"])
    print(f"Compressed Image S3 URL: {results['compressed_s3_url']}")
    print(f"Metadata-Embedded Image S3 URL: {results['metadata_s3_url']}")
    print("Timestamps:")
    print(f"Compression Time: {timestamps['compression_time']:.2f} seconds")
    print(f"Encryption Time: {timestamps['encryption_time']:.2f} seconds")
    print(f"Metadata Embedding Time: {timestamps['metadata_embedding_time']:.2f} seconds")
    print(f"Overall Time: {timestamps['overall_time']:.2f} seconds")
    print("#########################\n")

    results['timestamps'] = timestamps  # Include timestamps in results
    return status, results



# Streamlit UI
st.title("Batch Image Processing Workflow with Detailed Status Updates")

uploaded_files = st.file_uploader("Upload Images (Max: 5)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
password = st.text_input("Enter a password for encryption", type="password")

if st.button("Submit"):
    if not uploaded_files or not password:
        st.error("Please upload at least one image and enter a password.")
    elif len(uploaded_files) > 5:
        st.error("You can upload a maximum of 5 images at a time.")
    else:
        with ThreadPoolExecutor() as executor:
            for uploaded_file in uploaded_files:
                st.write(f"### Processing `{uploaded_file.name}`")
                status_placeholder = st.empty()  # Placeholder for updating status dynamically

                # Process the file and get status updates
                status_updates, results = process_image(uploaded_file, password)

                # Display each status update dynamically
                for update in status_updates:
                    status_placeholder.write(update)
                    st.write(f"✔ {update}")  # Show success messages dynamically
                
                # Optionally, show a success message for overall completion
                if results:
                    st.success(f"Processing complete for `{uploaded_file.name}`.")
