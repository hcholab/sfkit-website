import pytest
from src.gwas import get_status, run_gwas


def test_index(client):
    response = client.get("/index")
    assert b"Log In" in response.data
    assert b"Register" in response.data
    assert b"Secure GWAS" in response.data


def test_create(client, auth):
    auth.register()
    auth.login()
    assert client.get("create").status_code == 200
    response = client.post(
        "create", data={"title": "test title", "description": "test description"}
    )
    assert response.headers["Location"] == "http://localhost/index"


def test_create_no_title(client, auth):
    auth.register()
    auth.login()
    response = client.post("create", data={"title": "", "description": ""})
    assert "Location" not in response.headers


@pytest.mark.parametrize(
    ("title", "description"),
    (
        ("testtitle", "test description"),
        ("testtitle2", "test description"),
    ),
)
def test_update(client, auth, title, description):
    auth.register()
    auth.login()
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    assert client.get("update/testtitle").status_code == 200
    response = client.post(
        "update/testtitle",
        data={"title": title, "description": description},
    )
    assert response.headers["Location"] == "http://localhost/index"


def test_update_no_title(client, auth):
    auth.register()
    auth.login()
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    response = client.post("update/testtitle", data={"title": "", "description": ""})
    assert "Location" not in response.headers


def test_delete(client, auth):
    auth.register()
    auth.login()
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    response = client.post("delete/testtitle")
    assert response.headers["Location"] == "http://localhost/index"


def test_join_project(client, auth):
    auth.register()
    auth.login()

    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    response = client.post("join/testtitle")
    assert response.headers["Location"] == "http://localhost/index"


def test_start(app, client, auth, mocker):
    auth.register()
    auth.login()
    client.post(
        "auth/user/a%40a.a", data={"id": "a@a.a", "gcp_project": "broad-cho-priv1"}
    )
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    assert client.get("start/testtitle/100").status_code == 200

    auth.logout()
    auth.register(email="b@b.b", password="b", password_check="b")
    auth.login(email="b@b.b", password="b")
    client.post(
        "auth/user/b%40b.b", data={"id": "b@b.b", "gcp_project": "broad-cho-priv1"}
    )
    client.post("join/testtitle")

    client.post("start/testtitle/1")
    auth.logout()
    auth.login()

    mocker.patch("src.gwas.run_gwas", mock_run_gwas)
    client.post("start/testtitle/0")
    mocker.patch("src.gwas.get_status", mock_get_status)
    client.post("start/testtitle/0")


def test_get_status(mocker):
    mocker.patch("src.gwas.GoogleCloudPubsub", MockGoogleCloudPubsub)
    mocker.patch("src.gwas.GoogleCloudCompute", MockGoogleCloudCompute)

    assert get_status("role", "gcp_project", "test", "project title") == "test"
    assert (
        get_status("role", "gcp_project", "GWAS Completed!", "project title")
        == "GWAS Completed!"
    )
    assert (
        get_status("3", "gcp_project", "DataSharing Completed!", "project title")
        == "DataSharing Completed!"
    )


def test_run_gwas(mocker):
    mocker.patch("src.gwas.GoogleCloudPubsub", MockGoogleCloudPubsub)
    mocker.patch("src.gwas.GoogleCloudCompute", MockGoogleCloudCompute)

    run_gwas("role", "gcp_project", "project title")


def mock_get_status(role, gcp_project, status, project_title):
    return status


def mock_run_gwas(role, gcp_project, project_title):
    return True


# class to mock GoogleCloudCompute
class MockGoogleCloudCompute:
    def __init__(self, project):
        pass

    def setup_networking(self, role):
        pass

    def setup_instance(self, zone, instance, role):
        pass

    def get_service_account_for_vm(self, zone, instance):
        return "serviceaccount"

    def stop_instance(self, zone, role):
        pass


# class to mock GoogleCloudPubsub
class MockGoogleCloudPubsub:
    def __init__(self, project, role, project_title):
        pass

    def create_topic_and_subscribe(self):
        pass

    def add_pub_iam_member(self, role, member):
        pass

    def listen_to_startup_script(self, status):
        return status
