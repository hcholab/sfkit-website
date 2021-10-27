import pytest
from src import create_app
from mockfirestore import MockFirestore


@pytest.fixture
def app(mocker):
    mocker.patch("src.firestore.Client", MockFirestore)
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


class MockGoogleCloudIAM:
    def __init__(self):
        pass

    def give_cloud_build_view_permissions(self, email):
        pass


class AuthActions:
    def __init__(self, client, mocker):
        self._client = client
        self._mocker = mocker

    def register(self, email="a@a.a", password="a", password_check="a"):
        self._mocker.patch("src.auth.GoogleCloudIAM", MockGoogleCloudIAM)
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

    def callback(
        self,
        credential="eyJhbGciOiJSUzI1NiIsImtpZCI6ImJiZDJhYzdjNGM1ZWI4YWRjOGVlZmZiYzhmNWEyZGQ2Y2Y3NTQ1ZTQiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJuYmYiOjE2MzUyNjExNjQsImF1ZCI6IjQxOTAwMzc4NzIxNi1yY2lmMzRyOTc2YTlxbTM4MThxZ2VxZWQ3YzU4Mm9kNi5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbSIsInN1YiI6IjEwNDM4MzY4NTk1NDM2NDQ4NzY5MiIsImVtYWlsIjoiYUBhLmEiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiYXpwIjoiNDE5MDAzNzg3MjE2LXJjaWYzNHI5NzZhOXFtMzgxOHFnZXFlZDdjNTgyb2Q2LmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwibmFtZSI6IlNpbW9uIE1lbmRlbHNvaG4iLCJwaWN0dXJlIjoiaHR0cHM6Ly9saDMuZ29vZ2xldXNlcmNvbnRlbnQuY29tL2EvQUFUWEFKeVphUFc3X1VOb1F5VHE2SjN5RjdrOFk0ZWF4MlUxZmM1WlAteTM9czk2LWMiLCJnaXZlbl9uYW1lIjoiYSIsImZhbWlseV9uYW1lIjoiYSIsImlhdCI6MTYzNTI2MTQ2NCwiZXhwIjoxNjM1MjY1MDY0LCJqdGkiOiJjYzM2MmViMDBiY2RhZDU2MjVkZDgwODQwZjJjNDI5ZWU4ZWY3YWMyIn0.QoBNH0e_2NFmR8S1w1YB2lsYqvXGlf517asLLlJZZLH2O18IgHvsFPGi8cB83kEd3Zx604Ej8Q4KFDJadGJl9hFEbmjm-oR_V4UdDQw9O1bqQVXhjk2oWXs8NFQ81g5TGlMMz0WG1tdrVv5t-wUttGVTD1j_HLVIg88DeJwPpbEdSTucp-dcjeCTsJo80RcinXt0omqyB8NjtUfZdKYnbDPvyf2hbMj-ocfSex31t-JWDquctyWQI0hy7rUJ5CcR9ydJtvxdyn191LS8YBdXo6m-bMfNCp7Hg-CXgc3Z5mNXZIYX-C9OasunECccfE6P2k2zXMfpSFW6XTY33Jn3uA",
    ):
        self._mocker.patch("src.auth.GoogleCloudIAM", MockGoogleCloudIAM)
        return self._client.post("/auth/callback", data={"credential": credential})

    def logout(self):
        return self._client.get("/auth/logout")


@pytest.fixture
def auth(client, mocker):
    return AuthActions(client, mocker)
