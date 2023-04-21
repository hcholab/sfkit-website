from io import BytesIO
from typing import Callable, Generator

from google.api_core.exceptions import GoogleAPIError
from pytest_mock import MockerFixture
from werkzeug.datastructures import FileStorage

from src.utils.google_cloud.google_cloud_storage import (
    download_blob_to_bytes,
    download_blob_to_filename,
    upload_blob_from_file,
    upload_blob_from_filename,
)


def test_upload_blob_from_filename(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", create_mock_storage_client)
    assert upload_blob_from_filename("bucket_name", "source_file_name", "destination_blob_name")

    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", create_mock_storage_client_fail)
    assert not upload_blob_from_filename("bucket_name", "source_file_name", "destination_blob_name")


def test_download_blob_to_filename(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", create_mock_storage_client)
    assert download_blob_to_filename("bucket_name", "source_blob_name", "destination_file_name")

    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", create_mock_storage_client_fail)
    assert not download_blob_to_filename("bucket_name", "source_blob_name", "destination_file_name")


def test_upload_blob_from_file(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", create_mock_storage_client)
    file_storage = FileStorage(stream=BytesIO(b"test data"), filename="test.txt")
    assert upload_blob_from_file("bucket_name", file_storage, "destination_blob_name")

    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", create_mock_storage_client_fail)
    assert not upload_blob_from_file("bucket_name", file_storage, "destination_blob_name")


def test_download_blob_to_bytes(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", create_mock_storage_client)
    result = download_blob_to_bytes("bucket_name", "source_blob_name")
    assert result == b"test content"

    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", create_mock_storage_client_fail)
    result = download_blob_to_bytes("bucket_name", "source_blob_name")
    assert result is None


def create_mock_storage_client(fail=False):
    return MockStorageClient(fail)


def create_mock_storage_client_fail():
    return MockStorageClient(fail=True)


class MockStorageClient:
    def __init__(self, fail=False):
        self.fail = fail

    def bucket(self, bucket_name):
        return MockBucket(bucket_name, self.fail)


class MockBucket:
    def __init__(self, bucket_name, fail=False):
        self.bucket_name = bucket_name
        self.fail = fail

    def blob(self, destination_blob_name):
        return MockBlob(destination_blob_name, self.fail)


class MockBlob:
    def __init__(self, destination_blob_name, fail=False):
        self.destination_blob_name = destination_blob_name
        self.fail = fail

    def upload_from_filename(self, source_file_name):
        if self.fail:
            raise GoogleAPIError("An error occurred.")

    def download_to_filename(self, destination_file_name):
        if self.fail:
            raise GoogleAPIError("An error occurred.")

    def upload_from_file(self, file_storage):
        if self.fail:
            raise GoogleAPIError("An error occurred.")

    def download_as_bytes(self):
        if self.fail:
            raise GoogleAPIError("An error occurred.")
        return b"test content"
