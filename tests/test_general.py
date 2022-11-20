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


def test_workflows(client):
    response = client.get("/workflows")
    assert response.status_code == 200
    assert b"Workflows" in response.data


def test_instructions_page(client):
    response = client.get("/instructions")
    assert response.status_code == 200
    assert b"Instructions" in response.data


def test_contact(client):
    response = client.get("/contact")
    assert response.status_code == 200
    assert b"Contact" in response.data


def test_update_notifications(client, auth, mocker):
    mocker.patch("src.general.remove_notification", mock_remove_notification)
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    response = client.post("/update_notifications", data=json.dumps({"data": "test"}))
    assert response.status_code == 200


def test_profile(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    response = client.get("/profile/a@a.com")
    assert response.status_code == 200
    assert b"Profile" in response.data


def test_edit_profile(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    response = client.get("/edit_profile")
    assert response.status_code == 200
    assert b"Profile" in response.data

    response = client.post("/edit_profile", data={"display_name": "test", "about": "test"})
    assert response.status_code == 302
    assert response.headers.get("Location") == "/profile/a%40a.com"


def mock_remove_notification(notification: str) -> None:
    pass
