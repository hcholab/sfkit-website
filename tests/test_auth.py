import pytest
from flask import g, session


@pytest.mark.parametrize(
    "path",
    ("/create", "/update/1", "/delete/1", "/join/1", "/start/1/1", "auth/user/1"),
)
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers["Location"] == "http://localhost/auth/login"


def test_register(client, app, auth):
    assert client.get("/auth/register").status_code == 200

    response = auth.register()
    assert response.headers["Location"] == "http://localhost/auth/login"

    with app.app_context():
        db = app.config["DATABASE"]
        assert db.collection("users").document("a@a.a").get().exists


@pytest.mark.parametrize(
    ("email", "password", "password_check", "message"),
    (
        ("", "", "", b"Email is required."),
        ("a@a.a", "", "", b"Password is required."),
        ("a@a.a", "a", "b", b"Passwords do not match."),
        ("a@a.a", "a", "a", b"Email already taken."),
    ),
)
def test_register_validate_input(auth, email, password, password_check, message):
    auth.register()
    response = auth.register(email, password, password_check)
    assert message in response.data


def test_login(client, auth):
    auth.register()
    assert client.get("/auth/login").status_code == 200
    response = auth.login()
    assert response.headers["Location"] == "http://localhost/index"

    with client:
        client.get("/")
        assert session["user_id"] == "a@a.a"
        assert g.user["email"] == "a@a.a"


@pytest.mark.parametrize(
    ("email", "password", "message"),
    (
        ("a", "b", b"Incorrect email."),
        ("a@a.a", "b", b"Incorrect password."),
    ),
)
def test_login_validate_input(client, auth, email, password, message):
    auth.register()
    response = client.post("/auth/login", data={"email": email, "password": password})
    assert message in response.data


def test_login_after_google_register(client, auth):
    auth.callback()
    response = client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
    assert b"Password did not check out" in response.data


def test_callback(app, auth):
    auth.callback()
    with app.app_context():
        db = app.config["DATABASE"]
        assert db.collection("users").document("a@a.a").get().exists


def test_callback_already_registered(auth):
    auth.register()
    auth.callback()


def test_user(client, auth):
    auth.register()
    auth.login()
    assert client.get("auth/user/a%40a.a", data={"id": "a@a.a"}).status_code == 200
    response = client.post(
        "auth/user/a%40a.a", data={"id": "a@a.a", "gcp_project": "broad-cho-priv1"}
    )
    assert response.headers["Location"] == "http://localhost/index"


def test_logout(client, auth):
    auth.register()
    auth.login()
    with client:
        auth.logout()
        assert "user_id" not in session
