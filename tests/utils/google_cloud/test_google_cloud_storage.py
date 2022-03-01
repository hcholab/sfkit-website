from src.utils.google_cloud.google_cloud_storage import GoogleCloudStorage
from src.utils import constants
from conftest import MockFirebaseAdminAuth


def test_add_bucket_iam_member(mocker):
    mocker.patch(
        "src.utils.google_cloud.google_cloud_storage.storage", MockMakeMockStorage
    )
    google_cloud_storage = GoogleCloudStorage("project")
    google_cloud_storage.add_bucket_iam_member("bucket_name", "role", "member")


def test_copy_parameters_to_bucket(app, client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch(
        "src.utils.google_cloud.google_cloud_storage.storage", MockMakeMockStorage
    )
    mocker.patch("src.utils.google_cloud.google_cloud_storage.fileinput", MockFileInput)
    google_cloud_storage = GoogleCloudStorage("project")

    auth.register()
    response = client.post(
        "create_study",
        data={
            "title": "study title",
            "description": "test description",
        },
    )
    assert response.headers["Location"] == "http://localhost/index"

    with app.app_context():
        google_cloud_storage.copy_parameters_to_bucket("study title", role="0")
        MockFileInput.return_garbage = True
        google_cloud_storage.copy_parameters_to_bucket("study title", role="0")


def test_upload_to_bucket(mocker):
    mocker.patch(
        "src.utils.google_cloud.google_cloud_storage.storage", MockMakeMockStorage
    )
    google_cloud_storage = GoogleCloudStorage("project")
    google_cloud_storage.upload_to_bucket("file", "filename")


def test_check_file_exists(mocker):
    mocker.patch(
        "src.utils.google_cloud.google_cloud_storage.storage", MockMakeMockStorage
    )
    google_cloud_storage = GoogleCloudStorage("project")
    assert not google_cloud_storage.check_file_exists("filename")


class MockMakeMockStorage:
    @staticmethod
    def Client(project):
        return MockStorage()


class MockStorage:
    def bucket(self, bucketName):
        return MockBucket()


class MockBucket:
    def get_iam_policy(self, requested_policy_version):
        return MockPolicy()

    def set_iam_policy(self, policy):
        pass

    def blob(self, filename):
        return MockBlob()

    def list_blobs(self):
        return []


class MockBlob:
    name = "filename"

    def download_to_filename(self, filename):
        pass

    def upload_from_filename(self, filename):
        pass

    def upload_from_file(self, file):
        pass


class MockPolicy:
    bindings = []


class MockFileInput:
    return_garbage = False

    @staticmethod
    def input(fine, inplace):
        return (
            ["asdf"]
            if MockFileInput.return_garbage
            else ["NUM_INDS 42", "NUM_SNPS 1000"]
        )
