import pytest

from conftest import MockFirebaseAdminAuth


@pytest.mark.parametrize(
    "path",
    ("/create", "/delete/1", "/start/1"),  # , "auth/user/1"),
)
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers.get("Location") == "http://localhost/auth/login"


def test_register(client, mocker):
    setup_mocking(mocker)

    response = client.get("/auth/register")
    assert response.status_code == 200

    response = client.post(
        "/auth/register",
        data={"email": "a@a.a", "password": "a", "password_check": "a"},
    )
    assert response.headers.get("Location") == "http://localhost/index"
    assert "a@a.a" in response.headers["Set-Cookie"]


@pytest.mark.parametrize(
    ("email", "password", "password_check", "message"),
    (
        ("a@a.a", "a", "b", "Passwords do not match."),
        ("duplicate", "a", "a", "This email is already registered."),
    ),
)
def test_register_validate_input(
    capfd, client, mocker, email, password, password_check, message
):
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
    assert response.headers["Location"] == "http://localhost/index"


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
        "/auth/callback",
        data={"credential": "bad"},
    )

    client.post(
        "/auth/callback",
        data={
            "credential": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImFAYS5hIiwiaWF0IjoxNTE2MjM5MDIyfQ.H8ImFl3EFlNM_nlS07cKOqZJsTjdXbYRuV8KWubADjo"
        },
    )

    client.post(
        "/auth/callback",
        data={
            "credential": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImJhZCIsImlhdCI6MTUxNjIzOTAyMn0.XY1kpbvla-z1h6kzkCciSIMGU_MCDTxZwaZzStOPkfE"
        },
    )


def test_logout(client, auth):
    client.get("/auth/logout")
    # TODO: check nothing in cookie


def setup_mocking(mocker):
    mocker.patch(
        "src.auth.sign_in_with_email_and_password", mock_sign_in_with_email_and_password
    )
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.auth.GoogleCloudIAM", MockGoogleCloudIAM)
    mocker.patch("src.auth.id_token.verify_oauth2_token", mock_verify_token)


def mock_verify_token(token, blah, blah2):
    if token == "bad":
        raise ValueError("Invalid token")


def mock_sign_in_with_email_and_password(email, password):
    if email == "bad":
        raise Exception(password)
    return {"idToken": email}


class MockGoogleCloudIAM:
    def give_cloud_build_view_permissions(self, email):
        pass
