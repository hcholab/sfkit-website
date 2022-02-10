import pytest
from mockfirestore import MockFirestore
from src import create_app


@pytest.fixture
def app(mocker):
    mocker.patch("src.firestore.Client", MockFirestore)
    mocker.patch("src.firebase_admin.initialize_app", return_value=None)
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client, mocker, app):
    return AuthActions(client, mocker, app)


class AuthActions:
    def __init__(self, client, mocker, app):
        self._client = client
        self._mocker = mocker
        self._app = app

    def register(self, email="a@a.a", password="a", password_check="a"):
        self.login(email, password)

    def login(self, email="a@a.a", password="a"):
        self._client.set_cookie("localhost", "session", email)

    def logout(self):
        self._client.set_cookie("localhost", "session")


class MockFirebaseAdminAuth:
    UserNotFoundError = Exception

    def create_user(email, password, uid=None):
        if not email:
            raise Exception()
        elif email == "duplicate":
            raise Exception("EMAIL_EXISTS")
        pass

    def create_session_cookie(user_token, expires_in=None):
        return user_token

    def verify_session_cookie(session_cookie, check_revoked=True):
        if session_cookie:
            return {"email": session_cookie, "uid": "uid".encode("utf-8")}
        raise Exception("session cookie provided: None")

    def get_user_by_email(email):
        if email == "bad":
            raise auth.UserNotFoundError("bad email")
        pass

    def update_user(uid, email, password):
        pass

    def create_custom_token(uid):
        return uid
