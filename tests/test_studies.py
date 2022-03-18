import io
from copy import deepcopy

from src.utils import constants

from conftest import MockFirebaseAdminAuth

test_create_data = {
    "title": "testtitle",
    "description": "test description",
    "study_information": "hi",
}


def test_index(client):
    response = client.get("/index")
    assert response.status_code == 200
    assert b"Log In" in response.data
    assert b"Register" in response.data
    assert b"Secure GWAS" in response.data


def test_study(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study", data=test_create_data)
    response = client.get("/study/testtitle")
    assert response.status_code == 200
    assert b"parameters" in response.data
    assert b"personal_parameters" in response.data


def test_download_public_key(app, client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    doc_ref = app.config["DATABASE"].collection("studies").document("testtitle")
    doc_ref.set(
        {
            "participants": ["a@a.com"],
            "personal_parameters": {"a@a.com": {"PUBLIC_KEY": {"value": "public_key"}}},
        }
    )

    response = client.get("/study/testtitle/download_public_key/1")
    assert response.status_code == 200
    assert b"public_key" in response.data


def test_upload_public_key(app, client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    doc_ref = app.config["DATABASE"].collection("studies").document("testtitle")
    doc_ref.set(
        {
            "personal_parameters": {
                "a@a.com": {"PUBLIC_KEY": {"value": "old_public_key"}}
            },
        }
    )

    client.post(
        "/study/testtitle/upload_public_key",
        data={"file": (io.BytesIO(b"new_public_key"), "")},
    )
    client.post(
        "/study/testtitle/upload_public_key",
        data={"file": (io.BytesIO(b"new_public_key"), "garbage.txt")},
    )
    assert (
        doc_ref.get().to_dict()["personal_parameters"]["a@a.com"]["PUBLIC_KEY"]["value"]
        == "old_public_key"
    )

    client.post(
        "/study/testtitle/upload_public_key",
        data={"file": (io.BytesIO(b"new_public_key"), "my_public_key.txt")},
    )
    assert (
        doc_ref.get().to_dict()["personal_parameters"]["a@a.com"]["PUBLIC_KEY"]["value"]
        == "new_public_key"
    )


def test_create_study(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    assert client.get("create_study").status_code == 200
    response = client.post("create_study", data=test_create_data)
    assert response.headers["Location"] == "http://localhost/parameters/testtitle"
    response = client.post("create_study", data=test_create_data)
    assert response.headers["Location"] == "http://localhost/create_study"


def test_delete_study(client, app, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.GoogleCloudCompute", MockGoogleCloudCompute)
    auth.login()

    client.post("create_study", data=test_create_data)
    response = client.post("delete_study/testtitle")
    assert response.headers["Location"] == "http://localhost/index"

    client.post("create_study", data=test_create_data)

    user_parameters = deepcopy(constants.DEFAULT_USER_PARAMETERS)
    user_parameters["GCP_PROJECT"]["value"] = "gcp_project"
    doc_ref = app.config["DATABASE"].collection("studies").document("testtitle")
    doc_ref.set(
        {"personal_parameters": {"a@a.com": user_parameters}},
        merge=True,
    )

    client.post("delete_study/testtitle")


def test_request_join_study(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study", data=test_create_data)
    response = client.get("request_join_study/testtitle")
    assert response.headers["Location"] == "http://localhost/index"


def test_approve_join_study(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study", data=test_create_data)

    auth.logout()
    auth.login("b@b.com", "b")
    client.get("request_join_study/testtitle")

    auth.logout()
    auth.login()
    response = client.get("approve_join_study/testtitle/b@b.com")
    assert response.headers["Location"] == "http://localhost/study/testtitle"


def test_parameters(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study", data=test_create_data)
    assert client.get("parameters/testtitle").status_code == 200

    response = client.post("parameters/testtitle", data={"save": "save"})
    assert response.headers["Location"] == "http://localhost/study/testtitle"

    response = client.post("parameters/testtitle")
    assert "Something went wrong" in str(response.headers)

    # response = client.post(
    #     "parameters/testtitle",
    #     data={
    #         "upload": "upload",
    #         "file": (io.BytesIO(b"abcdef"), ""),
    #     },
    #     content_type="multipart/form-data",
    # )
    # assert response.headers["Location"] == "http://localhost/parameters/testtitle"

    # response = client.post(
    #     "parameters/testtitle",
    #     data={"upload": "upload", "file": (io.BytesIO(b"abcdef"), "pos.txt")},
    #     content_type="multipart/form-data",
    # )
    # assert response.headers["Location"] == "http://localhost/study/testtitle"

    # response = client.post(
    #     "parameters/testtitle",
    #     data={"upload": "upload", "file": (io.BytesIO(b"abcdef"), "bad_file")},
    #     content_type="multipart/form-data",
    # )
    # assert response.headers["Location"] == "http://localhost/parameters/testtitle"

    # response = client.post("parameters/testtitle")
    # assert response.headers["Location"] == "http://localhost/parameters/testtitle"


def test_personal_parameters(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study", data=test_create_data)
    assert client.get("personal_parameters/testtitle").status_code == 200

    client.post("personal_parameters/testtitle", data={"NUM_INDS": "NUM_INDS"})


class MockGoogleCloudCompute:
    project: str

    def __init__(self, project):
        pass

    def setup_networking(self, role):
        pass

    def setup_instance(
        self, zone, instance, role, size, metadata=None, boot_disk_size=None
    ):
        pass

    def get_service_account_for_vm(self, zone, instance):
        return "serviceaccount"

    def stop_instance(self, zone, role):
        pass

    def list_instances(self):
        return ["blah", "secure-gwas-instance-1"]

    def delete_instance(self, instance):
        pass


class MockGoogleCloudStorage:
    return_value = False

    def __init__(self, project):
        pass

    def copy_parameters_to_bucket(self, study_title, role):
        pass

    def upload_to_bucket(self, file, filename):
        pass

    def add_bucket_iam_member(self, bucket_name, role, member):
        pass

    def check_file_exists(self, filename):
        return MockGoogleCloudStorage.return_value
