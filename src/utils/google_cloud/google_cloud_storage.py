from typing import Optional

from google.api_core.exceptions import GoogleAPIError
from google.cloud.storage import Client as StorageClient
from werkzeug.datastructures import FileStorage

from src.utils import custom_logging

logger = custom_logging.setup_logging(__name__)


def upload_blob_from_filename(bucket_name: str, source_file_name: str, destination_blob_name: str) -> bool:
    """Upload a file to a Google Cloud Storage bucket using its file name.

    :param bucket_name: The name of the GCS bucket.
    :param source_file_name: The path to the file to be uploaded.
    :param destination_blob_name: The name of the destination blob in the GCS bucket.
    :return: True if successful, False otherwise.
    """
    try:
        storage_client = StorageClient()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
    except GoogleAPIError as e:
        logger.error(f"Error uploading file {source_file_name} to {destination_blob_name}.")
        logger.error(e)
        return False

    logger.info(f"File {source_file_name} uploaded to {destination_blob_name}.")
    return True


def download_blob_to_filename(bucket_name: str, source_blob_name: str, destination_file_name: str) -> bool:
    """Download a blob from a Google Cloud Storage bucket and save it as a file.

    :param bucket_name: The name of the GCS bucket.
    :param source_blob_name: The name of the source blob in the GCS bucket.
    :param destination_file_name: The path to the file where the blob will be saved.
    :return: True if successful, False otherwise.
    """
    try:
        storage_client = StorageClient()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        blob.download_to_filename(destination_file_name)
    except GoogleAPIError as e:
        logger.error(
            f"Error downloading blob {source_blob_name} from bucket {bucket_name} to file {destination_file_name}."
        )
        logger.error(e)
        return False

    logger.info(
        f"Downloaded storage object {source_blob_name} from bucket {bucket_name} to file {destination_file_name}."
    )
    return True


def upload_blob_from_file(bucket_name: str, file_storage: FileStorage, destination_blob_name: str) -> bool:
    """Upload a file to a Google Cloud Storage bucket using FileStorage.

    :param bucket_name: The name of the GCS bucket.
    :param file_storage: The FileStorage object containing the file to be uploaded.
    :param destination_blob_name: The name of the destination blob in the GCS bucket.
    :return: True if successful, False otherwise.
    """
    try:
        storage_client = StorageClient()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_file(file_storage)
    except GoogleAPIError as e:
        logger.error(f"Error uploading file {file_storage.filename}: {e}")
        return False

    return True


def download_blob_to_bytes(bucket_name: str, source_blob_name: str) -> Optional[bytes]:
    """Download a blob from a Google Cloud Storage bucket and return the contents as bytes.

    :param bucket_name: The name of the GCS bucket.
    :param source_blob_name: The name of the source blob in the GCS bucket.
    :return: The contents of the blob as bytes if successful, None otherwise.
    """
    try:
        storage_client = StorageClient()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        return blob.download_as_bytes()
    except GoogleAPIError as e:
        logger.error(f"Error downloading blob {source_blob_name} from bucket {bucket_name}.")
        logger.error(e)
        return None
