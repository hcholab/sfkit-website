from conftest import MockFirebaseAdminAuth
from src.utils.google_cloud.google_cloud_storage import GoogleCloudStorage

test_create_data = {
    "title": "testtitle",
    "description": "test description",
    "study_information": "hi",
}

patch_prefix = "src.utils.google_cloud.google_cloud_storage"


def test_add_bucket_iam_member(mocker):
    google_cloud_storage = setup_mocking_and_get_storage(mocker)
    google_cloud_storage.add_bucket_iam_member("bucket_name", "role", "member")


def test_copy_parameters_to_bucket(mocker):
    google_cloud_storage = setup_mocking_and_get_storage(mocker)
    mocker.patch(
        f"{patch_prefix}.GoogleCloudStorage.update_parameters",
        return_value=None,
    )
    google_cloud_storage.copy_parameters_to_bucket("study title")


def test_update_parameters(app, mocker, auth, client):
    google_cloud_storage = setup_mocking_and_get_storage(mocker)
    auth.login()
    client.post(
        "create_study/GWAS",
        data=test_create_data,
    )
    doc_ref = app.config["DATABASE"].collection("studies").document("testtitle")
    doc_ref.set({"participants": ["Broad", "a@a.com", "a@a.com"]}, merge=True)

    with app.app_context():
        google_cloud_storage.update_parameters("test.par.1.txt", "testtitle")
        google_cloud_storage.update_parameters("test.par.1.txt", "testtitle")


def test_upload_to_bucket(mocker):
    google_cloud_storage = setup_mocking_and_get_storage(mocker)
    google_cloud_storage.upload_to_bucket("file", "filename")


def test_check_file_exists(mocker):
    google_cloud_storage = setup_mocking_and_get_storage(mocker)
    assert not google_cloud_storage.check_file_exists("filename")


def setup_mocking_and_get_storage(mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch(f"{patch_prefix}.storage", MockMakeMockStorage)
    mocker.patch(f"{patch_prefix}.fileinput", MockFileInput)

    return GoogleCloudStorage("project")


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
    @staticmethod
    def input(fine, inplace):
        return ["NUM_INDS 42", "NUM_SNPS 1000", "asdf"]
