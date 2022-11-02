import json

from conftest import MockFirebaseAdminAuth

test_create_data = {
    "title": "blah",
    "description": "test description",
    "study_information": "hi",
}


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"portal for running privacy-preserving distributed computation on genomic data" in response.data

    home_response = client.get("/home")
    assert home_response.status_code == 200
    assert home_response.data == response.data


def test_update_notifications(client, auth, mocker):
    mocker.patch("src.general.remove_notification", mock_remove_notification)
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    response = client.post("/update_notifications", data=json.dumps({"data": "test"}))
    assert response.status_code == 200


def test_instructions_page(client):
    response = client.get("/instructions")
    assert response.status_code == 200
    assert b"Instructions" in response.data


# def test_all_notifications(client, auth, mocker):
#     mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
#     auth.login()

#     response = client.get("/all_notifications")
#     assert response.status_code == 200
#     assert b"All Notifications" in response.data


# def test_index_from_pubsub(client, app, mocker):
#     mocker.patch("src.general.data_has_valid_size", mock_data_has_valid_size)
#     mocker.patch("src.general.data_has_valid_files", mock_data_has_valid_files)
#     mocker.patch("src.general.GoogleCloudCompute", MockGoogleCloudCompute)

#     doc_ref = app.config["DATABASE"].collection("studies").document("blah")
#     doc_ref.set(
#         {"status": {"a@a.com": ["not ready"]}, "participants": ["Broad", "a@a.com"]},
#         merge=True,
#     )

#     assert client.post("/").status_code == 400

#     headers = {"Content-Type": "application/json"}

#     data = json.dumps({"data": "test"})
#     assert client.post("/", data=data, headers=headers).status_code == 400

#     data = json.dumps({"message": "blah"})
#     assert client.post("/", data=data, headers=headers).status_code == 400

#     # base64.b64encode("bad".encode("utf-8"))
#     data = json.dumps({"message": {"data": "YmFk"}})
#     assert client.post("/", data=data, headers=headers).status_code == 204

#     # base64.b64encode("blah-secure-gwas0-validate|6|pos.txt".encode("utf-8"))
#     data = json.dumps({"message": {"data": "YmxhaC1zZWN1cmUtZ3dhczAtdmFsaWRhdGV8Nnxwb3MudHh0"}})
#     assert client.post("/", data=data, headers=headers).status_code == 204

#     # base64.b64encode("blah-secure-gwas1-blah".encode("utf-8"))
#     data = json.dumps({"message": {"data": "YmxhaC1zZWN1cmUtZ3dhczEtYmxhaA=="}})
#     assert client.post("/", data=data, headers=headers).status_code == 204

#     # base64.b64encode("blah-secure-gwas1-ready".encode("utf-8"))
#     data = json.dumps({"message": {"data": "YmxhaC1zZWN1cmUtZ3dhczEtcmVhZHk="}})
#     assert client.post("/", data=data, headers=headers).status_code == 204

#     # base64.b64encode("blah-secure-gwas1-validate|6|pos.txt".encode("utf-8"))
#     data = json.dumps({"message": {"data": "YmxhaC1zZWN1cmUtZ3dhczEtdmFsaWRhdGV8Nnxwb3MudHh0"}})
#     assert client.post("/", data=data, headers=headers).status_code == 204

#     # base64.b64encode("blah-secure-gwas1-validate|100|pos.txt".encode("utf-8"))
#     data = json.dumps({"message": {"data": "YmxhaC1zZWN1cmUtZ3dhczEtdmFsaWRhdGV8MTAwfHBvcy50eHQ="}})
#     assert client.post("/", data=data, headers=headers).status_code == 204


def mock_data_has_valid_size(size, dic_ref_dict, role):
    return size == 6


def mock_data_has_valid_files(files):
    return True


def mock_remove_notification(notification: str) -> None:
    pass


# class to mock GoogleCloudCompute
class MockGoogleCloudCompute:
    def __init__(self, project):
        pass

    def stop_instance(self, zone, instance):
        pass
