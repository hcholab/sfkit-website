import pytest
from flask import g, session

def test_register(client, app):
    assert client.get("/auth/register").status_code == 200
    response = client.post("/auth/register", data={"email": "a@a.a", "password": "a", "password_check": "a"})
    assert response.headers["Location"] == "http://localhost/auth/login"

    with app.app_context():
        db = app.config["DATABASE"]
        assert(db.collection('users').document("a@a.a").get().exists)


@pytest.mark.parametrize(
    ("email", "password", "password_check", "message"),
    (
        ("", "", "", b"Email is required."),
        ("a@a.a", "", "", b"Password is required."),
        ("a@a.a", "a", "b", b"Passwords do not match."),
        ("a@a.a", "a", "a", b"Email already taken."),
    ),
)
def test_register_validate_input(client, email, password, password_check, message):
    client.post("/auth/register", data={"email": "a@a.a", "password": "a", "password_check": "a"})
    response = client.post(
        "/auth/register", data={"email": email, "password": password, "password_check": password_check}
    )
    print(response.data)
    assert message in response.data


def test_login(client):
    client.post("/auth/register", data={"email": "a@a.a", "password": "a", "password_check": "a"})
    assert client.get("/auth/login").status_code == 200
    response = client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
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
def test_login_validate_input(client, email, password, message):
    client.post("/auth/register", data={"email": "a@a.a", "password": "a", "password_check": "a"})
    response = client.post("/auth/login", data={"email": email, "password": password})
    assert message in response.data


def test_logout(client):
    client.post("/auth/register", data={"email": "a@a.a", "password": "a", "password_check": "a"})
    client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
    with client:
        client.get("/auth/logout")
        assert "user_id" not in session

def test_user(client):
    response = client.post("auth/a%40a.a/user", data={"id": "a%40a.a", "gcp_project": "broad-cho-priv1"})
    assert response.headers["Location"] == "http://localhost/auth/login"

    client.post("/auth/register", data={"email": "a@a.a", "password": "a", "password_check": "a"})
    client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
    assert client.get("auth/a%40a.a/user", data={"id": "a@a.a"}).status_code == 200
    response = client.post("auth/a%40a.a/user", data={"id": "a@a.a", "gcp_project": "broad-cho-priv1"})
    assert response.headers["Location"] == "http://localhost/index"




