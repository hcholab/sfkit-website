import json
from typing import Callable, Generator

from conftest import AuthActions, MockFirebaseAdminAuth
from flask.testing import FlaskClient
from pytest_mock import MockerFixture

test_create_data = {
    "title": "blah",
    "description": "test description",
    "study_information": "hi",
}


def test_home(client: FlaskClient):
    response = client.get("/")
    assert response.status_code == 200

    home_response = client.get("/home")
    assert home_response.status_code == 200
    assert home_response.data == response.data


def test_workflows(client: FlaskClient):
    response = client.get("/workflows")
    assert response.status_code == 200
    assert b"Workflows" in response.data


def test_instructions_page(client: FlaskClient):
    response = client.get("/instructions")
    assert response.status_code == 200
    assert b"Instructions" in response.data


def test_tutorial_page(client: FlaskClient):
    response = client.get("/tutorial")
    assert response.status_code == 200
    assert b"Tutorial" in response.data


def test_contact(client: FlaskClient):
    response = client.get("/contact")
    assert response.status_code == 200
    assert b"Contact" in response.data


def test_update_notifications(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.general.remove_notification", mock_remove_notification)
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    response = client.post("/update_notifications", data=json.dumps({"data": "test"}))
    assert response.status_code == 200


def test_profile(client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    response = client.get("/profile/a@a.com")
    assert response.status_code == 200
    assert b"Profile" in response.data


def test_edit_profile(
    client: FlaskClient, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    response = client.get("/edit_profile")
    assert response.status_code == 200
    assert b"Profile" in response.data

    response = client.post("/edit_profile", data={"display_name": "test", "about": "test"})
    assert response.status_code == 302
    assert response.headers.get("Location") == "/profile/a%40a.com"


def test_sample_data(client: FlaskClient, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    # Success case
    sample_file_data = b"Sample file content"
    mocker.patch("src.general.download_blob_to_bytes", return_value=sample_file_data)
    response = client.get("/sample_data/test_workflow/1")

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert response.data == sample_file_data

    # Exception case
    failure_message = "Failed to download file"
    mocker.patch("src.general.download_blob_to_bytes", side_effect=Exception(failure_message))

    response = client.get("/sample_data/test_workflow/1")

    assert response.status_code == 500
    assert response.json == {"error": failure_message}


def mock_remove_notification(notification: str) -> None:
    pass
