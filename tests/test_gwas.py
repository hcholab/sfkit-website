import io

import pytest
from src.gwas import run_gwas

from conftest import MockFirebaseAdminAuth


def test_index(client):
    response = client.get("/index")
    assert b"Log In" in response.data
    assert b"Register" in response.data
    assert b"Secure GWAS" in response.data


def test_create(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.register()
    assert client.get("create").status_code == 200
    response = client.post(
        "create", data={"title": "test title", "description": "test description"}
    )
    assert response.headers["Location"] == "http://localhost/index"

    response = client.post(
        "create", data={"title": "test title", "description": "test description"}
    )
    assert response.headers["Location"] == "http://localhost/create"


@pytest.mark.parametrize(
    ("title", "description"),
    (
        ("testtitle", "test description"),
        ("testtitle2", "test description"),
    ),
)
def test_update(client, auth, title, description, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.register()
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    client.post(
        "create", data={"title": "anothertitle", "description": "test description"}
    )
    assert client.get("update/testtitle").status_code == 200
    response = client.post(
        "update/testtitle",
        data={"title": title, "description": description},
    )
    assert response.headers["Location"] == "http://localhost/index"

    response = client.post(
        "update/anothertitle",
        data={"title": title, "description": description},
    )
    assert "http://localhost/update" in response.headers["Location"]


def test_delete(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.gwas.GoogleCloudCompute", MockGoogleCloudCompute)
    auth.register()
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    response = client.post("delete/testtitle")
    assert response.headers["Location"] == "http://localhost/index"


def test_join_project(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.register()

    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    response = client.post("join/testtitle")
    assert response.headers["Location"] == "http://localhost/index"


def test_start(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)

    auth.register()
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    assert client.get("start/testtitle").status_code == 200

    auth.login()
    client.post(
        "personal_parameters/testtitle",
        data={"GCP_PROJECT": "gcp_project"},
    )

    auth.logout()
    auth.register(email="b@b.b", password="b", password_check="b")
    client.post("join/testtitle")

    auth.login(email="b@b.b", password="b")
    client.post("start/testtitle")

    auth.login(email="b@b.b", password="b")
    client.post(
        "personal_parameters/testtitle",
        data={"GCP_PROJECT": "gcp_project"},
    )

    mocker.patch("src.gwas.GoogleCloudStorage", MockGoogleCloudStorage)
    auth.login(email="b@b.b", password="b")
    client.post("start/testtitle")
    MockGoogleCloudStorage.return_value = True
    mocker.patch("src.gwas.GoogleCloudIAM", MockGoogleCloudIAM)
    auth.login(email="b@b.b", password="b")
    client.post("start/testtitle")
    MockGoogleCloudIAM.return_value = True
    auth.login(email="b@b.b", password="b")
    client.post("start/testtitle")

    auth.logout()
    auth.login()

    mocker.patch("src.gwas.run_gwas", mock_run_gwas)
    client.post("start/testtitle")
    # mocker.patch("src.gwas.get_status", mock_get_status)
    client.post("start/testtitle")


def test_parameters(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.gwas.GoogleCloudStorage", MockGoogleCloudStorage)
    auth.register()
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    assert client.get("parameters/testtitle").status_code == 200

    response = client.post("parameters/testtitle", data={"save": "save"})
    assert response.headers["Location"] == "http://localhost/start/testtitle"

    response = client.post(
        "parameters/testtitle",
        data={"upload": "upload", "file": (io.BytesIO(b"abcdef"), "")},
        content_type="multipart/form-data",
    )
    assert response.headers["Location"] == "http://localhost/parameters/testtitle"

    response = client.post(
        "parameters/testtitle",
        data={"upload": "upload", "file": (io.BytesIO(b"abcdef"), "pos.txt")},
        content_type="multipart/form-data",
    )
    assert response.headers["Location"] == "http://localhost/start/testtitle"

    response = client.post(
        "parameters/testtitle",
        data={"upload": "upload", "file": (io.BytesIO(b"abcdef"), "bad_file")},
        content_type="multipart/form-data",
    )
    assert response.headers["Location"] == "http://localhost/parameters/testtitle"

    with pytest.raises(SystemExit) as e:
        client.post("parameters/testtitle")
    assert e.type == SystemExit
    assert e.value.code == 1


def test_personal_parameters(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.register()
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    assert client.get("personal_parameters/testtitle").status_code == 200


# def test_get_status(mocker):
#     mocker.patch("src.gwas.GoogleCloudPubsub", MockGoogleCloudPubsub)
#     mocker.patch("src.gwas.GoogleCloudCompute", MockGoogleCloudCompute)

#     assert get_status("role", "gcp_project", "test", "project title") == "test"
#     assert (
#         get_status("role", "gcp_project", "finished", "project title")
#         == "GWAS Completed!"
#     )
#     assert (
#         get_status("role", "gcp_project", "GWAS Completed!", "project title")
#         == "GWAS Completed!"
#     )


def test_run_gwas(mocker):
    mocker.patch("src.gwas.GoogleCloudPubsub", MockGoogleCloudPubsub)
    mocker.patch("src.gwas.GoogleCloudCompute", MockGoogleCloudCompute)
    mocker.patch("src.gwas.GoogleCloudStorage", MockGoogleCloudStorage)

    run_gwas("role", "gcp_project", "project title", size=4)


def mock_get_status(role, gcp_project, status, project_title):
    return status


def mock_run_gwas(role, gcp_project, project_title, size):
    return True


# class to mock GoogleCloudCompute
class MockGoogleCloudCompute:
    def __init__(self, project):
        pass

    def setup_networking(self, role):
        pass

    def setup_instance(self, zone, instance, role, size):
        pass

    def get_service_account_for_vm(self, zone, instance):
        return "serviceaccount"

    def stop_instance(self, zone, role):
        pass


class MockGoogleCloudStorage:
    return_value = False

    def __init__(self, project):
        pass

    def copy_parameters_to_bucket(self, project_title, role):
        pass

    def upload_to_bucket(self, file, filename):
        pass

    def add_bucket_iam_member(self, bucket_name, role, member):
        pass

    def check_file_exists(self, filename):
        return MockGoogleCloudStorage.return_value


# class to mock GoogleCloudPubsub
class MockGoogleCloudPubsub:
    def __init__(self, project, role, project_title):
        pass

    def create_topic_and_subscribe(self):
        pass

    def delete_topic(self):
        pass

    def add_pub_iam_member(self, role, member):
        pass

    def listen_to_startup_script(self, status):
        return "GWAS Completed!" if status == "finished" else status


# class to mock GoogleCloudIAM
class MockGoogleCloudIAM:
    return_value = False

    def test_permissions(self, project_id):
        return MockGoogleCloudIAM.return_value


class MockFile:
    def __init__(self, filename):
        self.filename = filename
