import pytest


def test_index(client):
    response = client.get("/index")
    assert b"Log In" in response.data
    assert b"Register" in response.data


@pytest.mark.parametrize(
    "path",
    (
        "/create",
        "/update/1",
        "/delete/1",
    ),
)
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers["Location"] == "http://localhost/auth/login"


def test_create(client):
    client.post(
        "/auth/register",
        data={"email": "a@a.a", "password": "a", "password_check": "a"},
    )
    client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
    assert client.get("create").status_code == 200
    response = client.post(
        "create", data={"title": "test title", "description": "test description"}
    )
    assert response.headers["Location"] == "http://localhost/index"


def test_update(client):
    client.post(
        "/auth/register",
        data={"email": "a@a.a", "password": "a", "password_check": "a"},
    )
    client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    assert client.get("update/testtitle").status_code == 200
    response = client.post(
        "update/testtitle",
        data={"title": "testtitle", "description": "test description"},
    )
    assert response.headers["Location"] == "http://localhost/index"


def test_delete(client):
    client.post(
        "/auth/register",
        data={"email": "a@a.a", "password": "a", "password_check": "a"},
    )
    client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    response = client.post("delete/testtitle")
    assert response.headers["Location"] == "http://localhost/index"


def test_join_project(client):
    client.post(
        "/auth/register",
        data={"email": "a@a.a", "password": "a", "password_check": "a"},
    )
    client.post("/auth/login", data={"email": "a@a.a", "password": "a"})
    client.post(
        "create", data={"title": "testtitle", "description": "test description"}
    )
    response = client.post("join/testtitle")
    assert response.headers["Location"] == "http://localhost/index"
