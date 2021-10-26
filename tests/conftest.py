import pytest
from src import create_app
from mockfirestore import MockFirestore
import os


@pytest.fixture
def app():
    return create_app(
        {
            "SECRET_KEY": os.urandom(12).hex(),
            "TESTING": True,
            "DATABASE": MockFirestore(),
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


class mockGoogleCloudIAM:
    def __init__(self):
        pass

    def give_cloud_build_view_permissions(self, email):
        pass


class AuthActions:
    def __init__(self, client, mocker):
        self._client = client
        self._mocker = mocker

    def register(self, email="a@a.a", password="a", password_check="a"):
        self._mocker.patch("src.auth.GoogleCloudIAM", mockGoogleCloudIAM)
        return self._client.post(
            "/auth/register",
            data={
                "email": email,
                "password": password,
                "password_check": password_check,
            },
        )

    def login(self, email="a@a.a", password="a"):
        return self._client.post(
            "/auth/login", data={"email": email, "password": password}
        )

    def logout(self):
        return self._client.get("/auth/logout")


@pytest.fixture
def auth(client, mocker):
    return AuthActions(client, mocker)
