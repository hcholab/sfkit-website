from src.utils.google_cloud.google_cloud_storage import download_blob_to_filename, upload_blob_from_filename


def test_upload_blob(mocker):
    # mock storage.Client
    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", MockStorageClient)
    upload_blob_from_filename("bucket_name", "source_file_name", "destination_blob_name")


def test_download_blob(mocker):
    # mock storage.Client
    mocker.patch("src.utils.google_cloud.google_cloud_storage.storage.Client", MockStorageClient)
    download_blob_to_filename("bucket_name", "source_blob_name", "destination_file_name")

    MockBlob.fail = True
    download_blob_to_filename("bucket_name", "source_blob_name", "destination_file_name")


class MockStorageClient:
    def bucket(self, bucket_name):
        return MockBucket(bucket_name)


class MockBucket:
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name

    def blob(self, destination_blob_name):
        return MockBlob(destination_blob_name)


class MockBlob:
    fail = False

    def __init__(self, destination_blob_name):
        self.destination_blob_name = destination_blob_name

    def upload_from_filename(self, source_file_name):
        pass

    def download_to_filename(self, destination_file_name):
        # sourcery skip: raise-specific-error
        if self.fail:
            raise Exception
