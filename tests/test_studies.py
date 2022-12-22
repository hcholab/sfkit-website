from io import StringIO

from conftest import MockFirebaseAdminAuth
from python_http_client.exceptions import HTTPError
from sendgrid.helpers.mail import Mail
from werkzeug import Response

from src.studies import email, setup_gcp

test_create_data = {
    "title": "testtitle",
    "description": "test description",
    "study_information": "hi",
    "private_study": "on",
}


def test_index(client):
    response = client.get("/index")
    assert response.status_code == 200
    assert b"Log In" in response.data
    assert b"Register" in response.data


def test_study(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)
    response = client.get("/study/testtitle")
    assert response.status_code == 200
    assert b"parameters" in response.data
    assert b"personal_parameters" in response.data


def test_choose_study_type(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()

    response = client.post(
        "choose_study_type", data={"CHOOSE_STUDY_TYPE": "MPCGWAS", "SETUP_CONFIGURATION": "website"}
    )

    assert response.status_code == 302  # 302 is a redirect
    assert response.headers.get("Location") == "/create_study/MPCGWAS/website"


def test_create_study(client, auth, mocker):
    # sourcery skip: extract-duplicate-method
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()

    response = client.get("create_study/MPCGWAS/website")
    assert response.status_code == 200

    response = client.post("create_study/MPCGWAS/website", data=test_create_data)
    assert response.status_code == 302
    assert response.headers.get("Location") == "/parameters/testtitle"

    # again to assert that the study is not created twice
    response = client.post("create_study/MPCGWAS/website", data=test_create_data)
    assert response.status_code == 302
    assert response.headers.get("Location") == "/create_study/MPCGWAS/website"


def test_delete_study(client, app, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.GoogleCloudCompute", MockGoogleCloudCompute)
    auth.login()

    client.post("create_study/MPCGWAS/website", data=test_create_data)
    response = client.post("delete_study/testtitle")
    assert response.status_code == 302
    assert response.headers.get("Location") == "/index"

    client.post("create_study/MPCGWAS/website", data=test_create_data)


def test_request_join_study(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)
    response = client.post("request_join_study/testtitle", data={"message": "hi"})
    assert response.status_code == 302
    assert response.headers.get("Location") == "/index"

    auth.logout()
    auth.login("b@b.com", "b")
    client.post("request_join_study/testtitle", data={"message": "hi"})


def test_invite_participant(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.email", return_value=200)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)
    response = client.post("invite_participant/testtitle", data={"invite_participant_email": "b@b.com"})
    assert response.status_code == 302
    assert response.headers.get("Location") == "/study/testtitle"

    mocker.patch("src.studies.email", return_value=404)
    client.post("invite_participant/testtitle", data={"invite_participant_email": "b@b.com"})


def test_email(app, client, auth, mocker):
    with app.app_context():
        mocker.patch("src.studies.SendGridAPIClient", MockSendGridAPIClient)
        email("a@a.com", "b@b.com", "", "study_title")
        email("a@a.com", "b@b.com", "invitation_message", "study_title")
        email("a@a.com", "c@b.com", "invitation_message", "study_title")


def test_approve_join_study(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)

    auth.logout()
    auth.login("b@b.com", "b")
    client.post("request_join_study/testtitle", data={"message": "hi"})

    auth.logout()
    auth.login()
    response = client.get("approve_join_study/testtitle/b@b.com")
    assert "/study/testtitle" in response.headers.get("Location")


def test_accept_invitation(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.email", return_value=200)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)
    client.post("invite_participant/testtitle", data={"invite_participant_email": "b@b.com"})

    auth.logout()
    auth.login("b@b.com", "b")
    response = client.get("accept_invitation/testtitle")
    assert response.status_code == 302
    assert response.headers.get("Location") == "/study/testtitle"


def test_study_information(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)

    response = client.post(
        "study/testtitle/study_information",
        data={"study_description": "new description", "study_information": "new information"},
    )
    assert response.status_code == 302
    assert response.headers.get("Location") == "/study/testtitle"


def test_parameters(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)

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


def test_download_key_file(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)

    response = client.get("study/testtitle/download_key_file")
    assert response.status_code == 200
    print(response.headers.get("Content-Disposition"))
    assert response.headers.get("Content-Disposition") == "attachment; filename=auth_key.txt"

    client.get("study/testtitle/download_key_file")


def test_download_results_file(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    # mock os.makedirs
    mocker.patch("os.makedirs")
    # mock download_blob
    mocker.patch("src.studies.download_blob")
    # mock open to return a mock file
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)

    mocker.patch("src.studies.open", return_value=StringIO(""))
    response = client.get("study/testtitle/download_results_file")
    assert response.status_code == 200
    assert response.headers.get("Content-Disposition") == "attachment; filename=assoc.txt"

    mocker.patch("src.studies.open", side_effect=FileNotFoundError)
    client.get("study/testtitle/download_results_file")


def test_personal_parameters(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)
    client.post("personal_parameters/testtitle", data={"NUM_INDS": "NUM_INDS"})
    client.post("personal_parameters/testtitle", data={"NUM_CPUS": "42"})


def test_start_protocol(client, auth, app, mocker):
    # sourcery skip: docstrings-for-classes, no-long-functions, require-parameter-annotation, require-return-annotation
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.setup_gcp", lambda *args, **kwargs: None)
    mocker.patch("src.studies.GoogleCloudIAM", MockGoogleCloudIAM)
    # mock make_auth_key
    mocker.patch("src.studies.make_auth_key")

    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)
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

    doc_ref_dict["status"]["a@a.com"] = "running protocol SFGWAS"
    doc_ref.set(doc_ref_dict)
    client.post("study/testtitle/start_protocol")


def test_setup_gcp(client, auth, app, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.studies.GoogleCloudCompute", MockGoogleCloudCompute)
    auth.login()
    client.post("create_study/MPCGWAS/website", data=test_create_data)
    doc_ref = app.config["DATABASE"].collection("studies").document("testtitle")
    setup_gcp(doc_ref, "1")


class MockGoogleCloudCompute:
    project: str

    def __init__(self, study, project):
        pass

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


class MockSendGridAPIClient:
    def __init__(self, api_key):
        pass

    def send(self, message: Mail) -> Response:
        response = Response()

        if message.get()["personalizations"][0]["to"][0]["email"] == "c@b.com":
            raise HTTPError(400, "Bad Request", "Bad Request", {})
        else:
            response.status_code = 202
        return response


class MockGoogleCloudIAM:
    def test_permissions(self, gcp_project: str) -> bool:
        return gcp_project != "BAD"
