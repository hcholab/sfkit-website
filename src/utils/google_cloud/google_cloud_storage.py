from google.cloud import storage


def upload_blob(bucket_name: str, source_file_name: str, destination_blob_name: str) -> bool:
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
    except Exception as e:
        print(f"Error uploading file {source_file_name} to {destination_blob_name}.")
        print(e)

        return False

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

    return True


def download_blob(bucket_name: str, source_blob_name: str, destination_file_name: str) -> bool:
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        blob.download_to_filename(destination_file_name)
    except Exception as e:
        print(f"Error downloading blob {source_blob_name} from bucket {bucket_name} to file {destination_file_name}.")
        print(e)

        return False

    print(f"Downloaded storage object {source_blob_name} from bucket {bucket_name} to file {destination_file_name}.")

    return True
