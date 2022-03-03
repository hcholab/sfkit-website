import json

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


def test_instructions_page(client):
    response = client.get("/instructions")
    assert response.status_code == 200
    assert b"Instructions" in response.data


# test permissions page
def test_permissions_page(client):
    response = client.get("/permissions")
    assert response.status_code == 200
    assert b"Permissions" in response.data


def test_index_from_pubsub(client, app, mocker):
    mocker.patch("src.general.data_is_valid", mock_data_is_valid)

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
        {"message": {"data": "YmxhaC1ibGFoLWJsYWg="}}
    )  # base64.b64encode("blah-blah-blah".encode("utf-8"))
    assert client.post("/", data=data, headers=headers).status_code == 204

    data = json.dumps(
        {"message": {"data": "YmxhaC0xLWJsYWg="}}
    )  # base64.b64encode("blah-1-blah".encode("utf-8"))
    assert client.post("/", data=data, headers=headers).status_code == 204

    data = json.dumps(
        {"message": {"data": "YmxhaC0xLTY="}}
    )  # base64.b64encode("blah-1-6".encode("utf-8"))
    assert client.post("/", data=data, headers=headers).status_code == 204

    data = json.dumps(
        {"message": {"data": "YmxhaC0xLTU="}}
    )  # base64.b64encode("blah-1-5".encode("utf-8"))
    assert client.post("/", data=data, headers=headers).status_code == 204


def mock_data_is_valid(size, dic_ref_dict, role):
    return size == 6
