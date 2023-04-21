import datetime
from typing import Callable, Generator

from conftest import AuthActions, MockFirebaseAdminAuth
from flask import Flask
from flask.testing import FlaskClient
from pytest_mock import MockerFixture

test_create_data = {
    "title": "testtitle",
    "description": "test description",
    "study_information": "hi",
    "private_study": "on",
}


def test_index(app: Flask, client: FlaskClient, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    # sourcery skip: extract-duplicate-method, inline-immediately-returned-variable
    db = app.config["DATABASE"]
    db.collection("studies").document("testtitle").set(
        {"title": "testtitle", "created": datetime.datetime.now(), "private": True}
    )
    db.collection("users").document("display_names").set({"testtitle": "testtitle"})

    mocker.patch("src.studies.is_developer", return_value=True)
    mocker.patch("src.studies.is_participant", return_value=True)

    response = client.get("/index")
    assert response.status_code == 200
    assert b"Log In" in response.data
    assert b"Register" in response.data

    mocker.patch("src.studies.is_developer", return_value=False)
    mocker.patch("src.studies.is_participant", return_value=False)
    response = client.get("/index")

    db.collection("studies").document("testtitle").set(
        {"title": "testtitle", "created": datetime.datetime.now(), "private": False}
    )
    response = client.get("/index")


def test_study(
    app: Flask, client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):  # sourcery skip: extract-duplicate-method
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.is_developer", return_value=True)
    mocker.patch("src.studies.os.makedirs")
    mocker.patch("src.studies.os.path.exists", return_value=True)
    mocker.patch("src.studies.download_blob_to_filename")

    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)
    db = app.config["DATABASE"]
    db.collection("studies").document("testtitle").set(
        {"status": {"a@a.com": "Finished protocol"}, "participants": ["a@a.com"]}, merge=True
    )
    response = client.get("/study/testtitle")
    assert response.status_code == 200
    assert b"parameters" in response.data
    assert b"personal_parameters" in response.data

    db.collection("studies").document("testtitle").set(
        {"status": {"a@a.com": "Finished protocol"}, "study_type": "SF-GWAS"}, merge=True
    )
    response = client.get("/study/testtitle")

    mocker.patch("src.studies.os.path.exists", return_value=False)
    response = client.get("/study/testtitle")

    db.collection("studies").document("testtitle").set({"study_type": "PCA"}, merge=True)
    response = client.get("/study/testtitle")

    mocker.patch("src.studies.os.path.exists", return_value=True)
    response = client.get("/study/testtitle")

    db.collection("studies").document("testtitle").set({"study_type": "BAD"}, merge=True)
    response = client.get("/study/testtitle")

    auth.logout()
    auth.login("anonymous_user", "anonymous_user")
    db.collection("users").document("anonymous_user").set({"secret_access_code": "testcode"}, merge=True)
    response = client.get("/study/testtitle")

    mocker.patch("src.studies.is_developer", return_value=False)
    response = client.get("/study/testtitle")


def test_anonymous_study(client: FlaskClient, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    study_title = "testtitle"
    user_id = "testuser"
    secret_acces_code = "testcode"

    mocker.patch("src.studies.update_user")
    client.get(f"/anonymous/study/{study_title}/{user_id}/{secret_acces_code}")

    mocker.patch("src.studies.update_user", side_effect=Exception())
    client.get(f"/anonymous/study/{study_title}/{user_id}/{secret_acces_code}")


def test_send_message(
    app: Flask, client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    # Mock Firebase Admin Auth
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)

    # Log in and create a study
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)

    # Prepare the message data
    message_data = {"message": "Hello, this is a test message"}

    response = client.post("/study/testtitle/send_message", data={"message": ""})

    # Test the send_message route
    response = client.post("/study/testtitle/send_message", data=message_data, follow_redirects=True)
    assert response.status_code == 200

    # Get the study from the database
    db = app.config["DATABASE"]
    doc_ref = db.collection("studies").document("testtitle")
    doc_ref_dict: dict = doc_ref.get().to_dict()

    # Verify that the message is added to the study's messages
    assert "messages" in doc_ref_dict
    assert len(doc_ref_dict["messages"]) == 1
    assert doc_ref_dict["messages"][0]["body"] == message_data["message"]

    # Cleanup the created study
    doc_ref.delete()


def test_choose_study_type(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()

    response = client.post(
        "choose_study_type", data={"CHOOSE_STUDY_TYPE": "MPC-GWAS", "SETUP_CONFIGURATION": "website"}
    )

    assert response.status_code == 302  # 302 is a redirect
    assert response.headers.get("Location") == "/create_study/MPC-GWAS/website"


def test_create_study(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    # sourcery skip: extract-duplicate-method
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()

    response = client.get("create_study/MPC-GWAS/website")
    assert response.status_code == 200

    response = client.post("create_study/MPC-GWAS/website", data=test_create_data)
    assert response.status_code == 302
    assert response.headers.get("Location") == "/parameters/testtitle"

    # again to assert that the study is not created twice
    response = client.post("create_study/MPC-GWAS/website", data=test_create_data)
    assert response.status_code == 302
    assert response.headers.get("Location") == "/create_study/MPC-GWAS/website"


def test_restart_study(
    app: Flask, client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.GoogleCloudCompute", MockGoogleCloudCompute)
    mocker.patch("src.studies.create_instance_name", return_value="blah")

    # Log in and create a study
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)

    # Get the study from the database
    db = app.config["DATABASE"]
    doc_ref = db.collection("studies").document("testtitle")
    doc_ref_dict: dict = doc_ref.get().to_dict()

    # Modify the study to simulate a "completed" status
    for participant in doc_ref_dict["participants"]:
        doc_ref_dict["status"][participant] = "Finished protocol"
        doc_ref_dict["personal_parameters"][participant]["PUBLIC_KEY"]["value"] = "dummy_public_key"
    doc_ref_dict["tasks"] = {"task1": "completed", "task2": "completed"}
    doc_ref.set(doc_ref_dict)

    # Test the restart_study route
    response = client.post("/restart_study/testtitle", follow_redirects=True)
    assert response.status_code == 200

    # Get the updated study from the database
    doc_ref_dict_updated: dict = doc_ref.get().to_dict()

    # Verify that the study's status and other parameters have been reset
    for participant in doc_ref_dict_updated["participants"]:
        if participant == "Broad":
            assert doc_ref_dict_updated["status"][participant] == "ready to begin protocol"
        else:
            assert doc_ref_dict_updated["status"][participant] == ""
        assert doc_ref_dict_updated["personal_parameters"][participant]["PUBLIC_KEY"]["value"] == ""
    assert doc_ref_dict_updated["tasks"] == {}

    # Cleanup the created study
    doc_ref.delete()


def test_delete_study(
    client: FlaskClient, app: Flask, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.GoogleCloudCompute", MockGoogleCloudCompute)
    auth.login()

    client.post("create_study/MPC-GWAS/website", data=test_create_data)
    response = client.post("delete_study/testtitle")
    assert response.status_code == 302
    assert response.headers.get("Location") == "/index"

    client.post("create_study/MPC-GWAS/website", data=test_create_data)


def test_request_join_study(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)

    response = client.post("request_join_study/testtitle", data={"message": "hi"})

    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)
    response = client.post("request_join_study/testtitle", data={"message": "hi"})
    assert response.status_code == 302
    assert response.headers.get("Location") == "/index"

    auth.logout()
    auth.login("b@b.com", "b")
    client.post("request_join_study/testtitle", data={"message": "hi"})


def test_invite_participant(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.email", return_value=200)
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)
    response = client.post("invite_participant/testtitle", data={"invite_participant_email": "b@b.com"})
    assert response.status_code == 302
    assert response.headers.get("Location") == "/study/testtitle"

    mocker.patch("src.studies.email", return_value=404)
    client.post("invite_participant/testtitle", data={"invite_participant_email": "b@b.com"})


def test_approve_join_study(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)

    auth.logout()
    auth.login("b@b.com", "b")
    client.post("request_join_study/testtitle", data={"message": "hi"})

    auth.logout()
    auth.login()
    response = client.get("approve_join_study/testtitle/b@b.com")
    assert "/study/testtitle" in response.headers.get("Location")  # type: ignore


def test_accept_invitation(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    # sourcery skip: extract-duplicate-method, inline-immediately-returned-variable
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.email", return_value=200)
    mocker.patch("src.studies.redirect_with_flash")

    # Create a study and invite a participant
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)
    client.post("invite_participant/testtitle", data={"invite_participant_email": "b@b.com"})

    auth.logout()

    # Test the case where the logged-in user is not invited to the study
    auth.login("c@c.com", "c")
    response = client.get("accept_invitation/testtitle")
    auth.logout()

    # Test the case where the logged-in user is invited to the study
    auth.login("b@b.com", "b")
    response = client.get("accept_invitation/testtitle")
    assert response.status_code == 302
    assert response.headers.get("Location") == "/study/testtitle"


def test_study_information(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)

    response = client.post(
        "study/testtitle/study_information",
        data={"study_description": "new description", "study_information": "new information"},
    )
    assert response.status_code == 302
    assert response.headers.get("Location") == "/study/testtitle"


def test_parameters(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)

    response = client.get("parameters/testtitle")
    assert response.status_code == 200

    response = client.post(
        "parameters/testtitle",
        data={
            "NUM_SNPS": "100",
            "ITER_PER_EVAL": "100",
            "NUM_INDSa@a.com": "100",
            "blah": "blah",
        },
    )
    assert response.status_code == 302
    assert response.headers.get("Location") == "/study/testtitle"


def test_download_key_file(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)

    response = client.get("study/testtitle/download_key_file")
    assert response.status_code == 200
    print(response.headers.get("Content-Disposition"))
    assert response.headers.get("Content-Disposition") == "attachment; filename=auth_key.txt"

    client.get("study/testtitle/download_key_file")


def test_personal_parameters(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)
    client.post("personal_parameters/testtitle", data={"NUM_INDS": "NUM_INDS"})
    client.post("personal_parameters/testtitle", data={"NUM_CPUS": "42"})


def test_download_results_file(
    client: FlaskClient, auth: AuthActions, app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    # Mock external functions
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.download_blob_to_filename")
    mocker.patch("src.studies.send_file")
    mocker.patch("src.studies.os.makedirs")
    mocker.patch("src.studies.send_file")
    mocker.patch("src.studies.add_file_to_zip")

    # Create a mock study
    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)

    study_title = "testtitle"

    # Test case when both result.txt and plot file download fail
    mocker.patch("src.studies.download_blob_to_filename", return_value=False)
    client.get(f"/study/{study_title}/download_results_file")

    # Test case when result.txt download succeeds, but plot file download fails
    mocker.patch("src.studies.download_blob_to_filename", side_effect=[True, False])
    client.get(f"/study/{study_title}/download_results_file")

    mocker.patch("src.studies.download_blob_to_filename", side_effect=[False, True])
    client.get(f"/study/{study_title}/download_results_file")

    auth.logout()


def test_start_protocol(
    client: FlaskClient, auth: AuthActions, app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    # sourcery skip: docstrings-for-classes, no-long-functions, require-parameter-annotation, require-return-annotation
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.setup_gcp", lambda *args, **kwargs: None)
    mocker.patch("src.studies.GoogleCloudIAM", MockGoogleCloudIAM)
    mocker.patch("src.studies.redirect_with_flash")
    mocker.patch("src.studies.time.sleep")
    mocker.patch("src.studies.make_auth_key")

    auth.login()
    client.post("create_study/MPC-GWAS/website", data=test_create_data)
    doc_ref = app.config["DATABASE"].collection("studies").document("testtitle")
    doc_ref_dict = doc_ref.get().to_dict()

    client.post("study/testtitle/start_protocol")

    doc_ref_dict["personal_parameters"]["a@a.com"]["NUM_INDS"]["value"] = 100
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")

    doc_ref_dict["personal_parameters"]["a@a.com"]["GCP_PROJECT"]["value"] = "BAD"
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")

    doc_ref_dict["personal_parameters"]["a@a.com"]["DATA_PATH"]["value"] = "TEST_DATA_PATH"
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")

    doc_ref_dict["personal_parameters"]["a@a.com"]["GCP_PROJECT"]["value"] = "TEST_GCP_PROJECT"
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")

    mocker.patch("os.environ.get", side_effect=lambda key: "not_development" if key == "FLASK_DEBUG" else None)
    doc_ref_dict["demo"] = False
    doc_ref_dict["personal_parameters"]["a@a.com"]["GCP_PROJECT"]["value"] = "broad-cho-priv1-test"
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")
    mocker.patch("os.environ.get", side_effect=None)
    doc_ref_dict["personal_parameters"]["a@a.com"]["GCP_PROJECT"]["value"] = "TEST_GCP_PROJECT"
    doc_ref_dict["demo"] = True
    doc_ref.set(doc_ref_dict)

    doc_ref_dict["status"]["a@a.com"] = "ready to begin sfkit"
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")

    doc_ref_dict["status"]["Broad"] = "ready to begin sfkit"
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")

    auth.logout()
    auth.login("b@b.com", "b")
    client.post("request_join_study/testtitle", data={"message": "hi"})
    auth.logout()
    auth.login()
    client.get("approve_join_study/testtitle/b@b.com")
    auth.logout()
    auth.login("b@b.com", "b")
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["personal_parameters"]["b@b.com"] = doc_ref_dict["personal_parameters"]["a@a.com"].copy()
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")

    auth.logout()
    auth.login("a@a.com", "a")
    client.post("study/testtitle/start_protocol")

    doc_ref_dict["status"]["a@a.com"] = "running protocol SF-GWAS"
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")


class MockGoogleCloudCompute:
    project: str

    def __init__(self, study_title, gcp_project):
        self.study_title = study_title
        self.gcp_project = gcp_project

    def delete_everything(self):
        pass

    def setup_networking(self, doc_ref_dict, role):
        pass

    def remove_conflicting_peerings(self, gcp_project: list = list()) -> bool:
        return True

    def setup_instance(self, name, role, metadata, num_cpus, boot_disk_size):
        pass

    def stop_instance(self, zone, role):
        pass

    def list_instances(self):
        return ["blah", "testtitle-secure-gwas-instance-1"]

    def delete_instance(self, instance):
        pass


class MockGoogleCloudIAM:
    def test_permissions(self, gcp_project: str) -> bool:
        return gcp_project != "BAD"
