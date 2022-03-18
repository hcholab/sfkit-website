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
    assert b"portal for securely running GWAS" in response.data

    home_response = client.get("/home")
    assert home_response.status_code == 200
    assert home_response.data == response.data


def test_update_notifications(client, auth, mocker):
    mocker.patch("src.general.remove_notification", mock_remove_notification)
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    response = client.post("/update_notifications", data=json.dumps({"data": "test"}))
    assert response.status_code == 200


# def test_instructions_page(client):
#     response = client.get("/instructions")
#     assert response.status_code == 200
#     assert b"Instructions" in response.data


# # test permissions page
# def test_permissions_page(client):
#     response = client.get("/permissions")
#     assert response.status_code == 200
#     assert b"Permissions" in response.data


def test_index_from_pubsub(client, app, mocker):
    mocker.patch("src.general.data_has_valid_size", mock_data_has_valid_size)
    mocker.patch("src.general.data_has_valid_files", mock_data_has_valid_files)

    doc_ref = app.config["DATABASE"].collection("studies").document("blah")
    doc_ref.set(
        {"status": {"a@a.com": ["not ready"]}, "participants": ["a@a.com"]},
        merge=True,
    )

    assert client.post("/").status_code == 400

    headers = {"Content-Type": "application/json"}

    data = json.dumps({"data": "test"})
    assert client.post("/", data=data, headers=headers).status_code == 400

    data = json.dumps({"message": "blah"})
    assert client.post("/", data=data, headers=headers).status_code == 400

    data = json.dumps(
        {"message": {"data": "YmFk"}}
    )  # base64.b64encode("bad".encode("utf-8"))
    assert client.post("/", data=data, headers=headers).status_code == 204

    data = json.dumps(
        {"message": {"data": "YmxhaC1zZWN1cmUtZ3dhczAtYmxhaA=="}}
    )  # base64.b64encode("blah-secure-gwas0-blah".encode("utf-8"))
    assert client.post("/", data=data, headers=headers).status_code == 204

    data = json.dumps(
        {"message": {"data": "YmxhaC1zZWN1cmUtZ3dhczAtdmFsaWRhdGV8Nnxwb3MudHh0"}}
    )  # base64.b64encode("blah-secure-gwas0-validate|6|pos.txt".encode("utf-8"))
    assert client.post("/", data=data, headers=headers).status_code == 204

    data = json.dumps(
        {"message": {"data": "YmxhaC1zZWN1cmUtZ3dhczAtdmFsaWRhdGV8MTAwfHBvcy50eHQ="}}
    )  # base64.b64encode("blah-secure-gwas0-validate|100|pos.txt".encode("utf-8"))
    assert client.post("/", data=data, headers=headers).status_code == 204


def mock_data_has_valid_size(size, dic_ref_dict, role):
    return size == 6


def mock_data_has_valid_files(files):
    return True


def mock_remove_notification(notification: str) -> None:
    pass
