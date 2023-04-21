from typing import Callable, Generator

import pytest
from conftest import MockFirebaseAdminAuth
from flask import Response, jsonify, make_response, redirect, url_for
from flask.testing import FlaskClient
from pytest_mock import MockerFixture
from werkzeug import Response

from src.auth import load_logged_in_user
from src.utils import logging

logger = logging.setup_logging(__name__)


def test_load_logged_in_user(mocker, app):
    with app.test_request_context():
        mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
        load_logged_in_user()
        MockFirebaseAdminAuth.throw_create_custom_token_exception = True
        load_logged_in_user()
        MockFirebaseAdminAuth.throw_verify_session_cookie_exception = True
        load_logged_in_user()

        MockFirebaseAdminAuth.throw_create_custom_token_exception = False
        MockFirebaseAdminAuth.throw_verify_session_cookie_exception = False


def test_remove_old_flash_messages(client, app):
    # Add a sample route to test the after_app_request function
    @app.route("/test_route")
    def test_route():
        return jsonify(success=True)

    # Test case: without a flash cookie
    response = client.get("/test_route")
    assert response.status_code == 200
    assert response.json == {"success": True}
    assert "flash" not in response.headers.get("Set-Cookie", "")

    # Test case: with a flash cookie
    client.set_cookie("localhost", "flash", "test_flash_message")
    response = client.get("/test_route")
    assert response.status_code == 200
    assert response.json == {"success": True}
    assert "flash" in response.headers.get("Set-Cookie", "")
    assert "flash=" in response.headers.get("Set-Cookie", "")
    assert "flash=test_flash_message" not in response.headers.get("Set-Cookie", "")


@pytest.mark.parametrize(
    "path",
    ("/create_study/GWAS/website", "/delete_study/1", "/study/1"),
)
def test_login_required(client, path):
    response = client.post(path)
    assert "auth/login" in response.headers.get("Location")


def test_register(client, mocker):
    setup_mocking(mocker)

    response = client.get("/auth/register")
    assert response.status_code == 200

    response = client.post(
        "/auth/register",
        data={"username": "a@a.a", "password": "a", "password_check": "a"},
    )
    assert "index" in response.headers.get("Location")


@pytest.mark.parametrize(
    ("username", "password", "password_check", "message"),
    (
        ("a@a.a", "a", "b", "Passwords do not match."),
        ("duplicate", "asdfasdf", "asdfasdf", "This username is already registered."),
        ("", "a", "a", "Error creating user"),
    ),
)
def test_register_validate_input(client, mocker, username, password, password_check, message):
    setup_mocking(mocker)

    response = client.post(
        "/auth/register",
        data={"username": username, "password": password, "password_check": password_check},
    )

    assert message in response.headers.get("Flash-Messages")


def test_login(client, mocker):
    setup_mocking(mocker)

    assert client.get("/auth/login").status_code == 200

    response = client.post("/auth/login", data={"username": "a@a.a", "password": "a"})
    assert "index" in response.headers.get("Location")


@pytest.mark.parametrize(
    ("username", "password", "message"),
    (
        ("bad", "INVALID_PASSWORD", "Invalid password"),
        ("bad", "USER_NOT_FOUND", "No user found with that username."),
        ("bad", "BAD", "Error logging in."),
    ),
)
def test_login_validate_input(caplog, client, mocker, username, password, message):
    setup_mocking(mocker)

    response = client.post("/auth/login", data={"username": username, "password": password})

    assert message in response.headers.get("Flash-Messages")


def test_logout(client, auth):
    auth.login()
    assert client.cookie_jar._cookies["localhost.local"]["/"]["session"].value == '"a@a.com"'

    client.get("/auth/logout")
    assert client.cookie_jar._cookies["localhost.local"]["/"]["session"].value == ""


def test_login_with_google_callback(client: FlaskClient, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    print("test_login_with_google_callback")
    setup_mocking(mocker)

    # Successful login case
    response = client.post(
        "/auth/login_with_google_callback", data={"credential": "good_token", "next": "studies.index"}
    )
    assert "index" in response.headers.get("Location", "")

    # Invalid token case
    response = client.post(
        "/auth/login_with_google_callback", data={"credential": "bad_token", "next": "studies.index"}
    )
    assert "index" in response.headers.get("Location", "")
    assert "Invalid Google account." in response.headers.get("Flash-Messages", "")

    # Test with a custom next redirect
    response = client.post(
        "/auth/login_with_google_callback", data={"credential": "good_token", "next": "custom_redirect"}
    )
    assert response.headers.get("Location") == "custom_redirect"


def setup_mocking(mocker):
    mocker.patch("src.auth.update_user", mock_update_user)
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.auth.GoogleCloudIAM", MockGoogleCloudIAM)
    mocker.patch("src.auth.id_token.verify_oauth2_token", mock_verify_token)
    mocker.patch("src.auth.create_user", mock_create_user)
    mocker.patch("src.auth.redirect_with_flash", mock_redirect_with_flash)


def mock_update_user(email: str, password: str, redirect_url: str = "") -> Response:
    if password == "INVALID_PASSWORD":
        logger.error("Invalid password")
        raise ValueError("INVALID_PASSWORD")
    elif password == "USER_NOT_FOUND":
        logger.error("No user found with that email.")
        raise ValueError("USER_NOT_FOUND")
    elif password == "BAD":
        logger.error("Error logging in.")
        raise ValueError("Error logging in.")
    return redirect(url_for("studies.index"))


def mock_verify_token(token, _, __):
    if token == "bad_token":
        raise ValueError("Invalid token")
    return {"email": token, "name": token}


def mock_sign_in_with_email_and_password(email, password):
    # sourcery skip: docstrings-for-classes, raise-specific-error, require-parameter-annotation, require-return-annotation
    if email == "bad":
        raise Exception(password)
    return {"idToken": email}


class MockGoogleCloudIAM:
    def give_minimal_required_gcp_permissions(self, email):
        pass


def mock_create_user(user_id, name, redirect_url):
    return redirect(redirect_url)


def mock_redirect_with_flash(url: str = "", location: str = "", message: str = "", error: str = "") -> Response:
    if location:
        url = url_for(location)
    response = make_response(redirect(url))
    if message or error:
        flash_messages = []
        if message:
            flash_messages.append(f"message:{message}")
        if error:
            flash_messages.append(f"error:{error}")
        response.headers["Flash-Messages"] = "|".join(flash_messages)
    return response
