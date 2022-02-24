import json


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"portal for securely running GWAS" in response.data

    home_response = client.get("/home")
    assert home_response.status_code == 200
    assert home_response.data == response.data


def test_workflow_page(client):
    response = client.get("/workflow")
    assert response.status_code == 200
    assert b"Workflow" in response.data


# test permissions page
def test_permissions_page(client):
    response = client.get("/permissions")
    assert response.status_code == 200
    assert b"Permissions" in response.data


def test_index_from_pubsub(client, app):
    with app.app_context():
        db = app.config["DATABASE"]
        doc_ref = db.collection("studies").document("blah")
        doc_ref.set({"status": ["", "", "", "", "", ""]})

    client.post("/")

    headers = {"Content-Type": "application/json"}
    data = json.dumps({"data": "test"})
    client.post("/", data=data, headers=headers)

    data = json.dumps({"message": "blah"})
    client.post("/", data=data, headers=headers)

    data = json.dumps(
        {"message": {"data": "YmxhaA=="}}
    )  # base64.b64encode("blah".encode("utf-8"))
    client.post("/", data=data, headers=headers)

    data = json.dumps(
        {"message": {"data": "YmxhaC1ibGFoLWJsYWg="}}
    )  # base64.b64encode("blah-blah-blah".encode("utf-8"))
    client.post("/", data=data, headers=headers)

    data = json.dumps(
        {"message": {"data": "YmxhaC01LWJsYWg="}}
    )  # base64.b64encode("blah-5-blah".encode("utf-8"))
    client.post("/", data=data, headers=headers)
