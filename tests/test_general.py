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
