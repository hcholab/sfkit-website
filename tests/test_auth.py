from flask import redirect, url_for
import jwt
from werkzeug import Response
import pytest

from conftest import MockFirebaseAdminAuth
from src.auth import load_logged_in_user


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
        data={"email": "a@a.a", "password": "a", "password_check": "a"},
    )
    assert "index" in response.headers.get("Location")


@pytest.mark.parametrize(
    ("email", "password", "password_check", "message"),
    (
        ("a@a.a", "a", "b", "Passwords do not match."),
        ("duplicate", "a", "a", "This email is already registered."),
        ("", "a", "a", "Error creating user"),
    ),
)
def test_register_validate_input(capfd, client, mocker, email, password, password_check, message):
    setup_mocking(mocker)

    client.post(
        "/auth/register",
        data={"email": email, "password": password, "password_check": password_check},
    )

    assert message in capfd.readouterr()[0]


def test_login(client, mocker):
    setup_mocking(mocker)

    assert client.get("/auth/login").status_code == 200

    response = client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
    assert "index" in response.headers.get("Location")


@pytest.mark.parametrize(
    ("email", "password", "message"),
    (
        ("bad", "INVALID_PASSWORD", "Invalid password"),
        ("bad", "USER_NOT_FOUND", "No user found with that email."),
        ("bad", "BAD", "Error logging in."),
    ),
)
def test_login_validate_input(capfd, client, mocker, email, password, message):
    setup_mocking(mocker)
    client.post("/auth/login", data={"email": email, "password": password})

    assert message in capfd.readouterr()[0]


def test_callback(client, app, auth, mocker):
    setup_mocking(mocker)

    client.post(
        "/auth/login_with_google_callback",
        data={"credential": "bad"},
    )

    response = client.post(
        "/auth/login_with_google_callback",
        data={
            "credential": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImFAYS5hIiwibmFtZSI6ImEiLCJpYXQiOjE1MTYyMzkwMjJ9.fx0D7FUvxuXhEZnP7ylFhVoJGDDTGTaOpARCd1Fqeco"
        },
    )

    assert response.status_code == 302
    assert response.headers.get("Location") == "/index"

    client.post(
        "/auth/login_with_google_callback",
        data={
            "credential": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImJhZCIsImlhdCI6MTUxNjIzOTAyMn0.XY1kpbvla-z1h6kzkCciSIMGU_MCDTxZwaZzStOPkfE"
        },
    )


def test_logout(client, auth):
    auth.login()
    assert client.cookie_jar._cookies["localhost.local"]["/"]["session"].value == '"a@a.com"'

    client.get("/auth/logout")
    assert client.cookie_jar._cookies["localhost.local"]["/"]["session"].value == ""


def setup_mocking(mocker):
    mocker.patch("src.auth.update_user", mock_update_user)
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.auth.GoogleCloudIAM", MockGoogleCloudIAM)
    mocker.patch("src.auth.id_token.verify_oauth2_token", mock_verify_token)


def mock_update_user(email: str, password: str, redirect_url: str = "") -> Response:
    if password == "INVALID_PASSWORD":
        print("Invalid password")
        raise ValueError("INVALID_PASSWORD")
    elif password == "USER_NOT_FOUND":
        print("No user found with that email.")
        raise ValueError("USER_NOT_FOUND")
    elif password == "BAD":
        print("Error logging in.")
        raise ValueError("Error logging in.")
    return redirect(url_for("studies.index"))


def mock_verify_token(token, blah, blah2):
    if token == "bad":
        raise ValueError("Invalid token")
    return jwt.decode(token, options={"verify_signature": False}, algorithms=["HS256"])


def mock_sign_in_with_email_and_password(email, password):
    # sourcery skip: docstrings-for-classes, raise-specific-error, require-parameter-annotation, require-return-annotation
    if email == "bad":
        raise Exception(password)
    return {"idToken": email}


class MockGoogleCloudIAM:
    def give_minimal_required_gcp_permissions(self, email):
        pass
