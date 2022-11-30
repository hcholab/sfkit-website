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

    def register(self, email="a@a.com", password="a", password_check="a"):
        self.login(email, password)

    def login(self, email="a@a.com", password="a"):
        self._client.set_cookie("localhost", "session", email)

    def logout(self):
        self._client.set_cookie("localhost", "session")


class MockFirebaseAdminAuth:
    UserNotFoundError = Exception
    throw_verify_session_cookie_exception = False
    throw_create_custom_token_exception = False

    @staticmethod
    def create_user(email, password, uid=None):
        # sourcery skip: do-not-use-staticmethod, docstrings-for-classes, raise-specific-error, require-parameter-annotation, require-return-annotation

        if not email:
            raise Exception()
        elif email == "duplicate":
            raise Exception("EMAIL_EXISTS")

    @staticmethod
    def create_session_cookie(user_token, expires_in=None):
        return user_token

    @staticmethod
    def verify_session_cookie(session_cookie, check_revoked=True):
        # sourcery skip: raise-specific-error
        if MockFirebaseAdminAuth.throw_verify_session_cookie_exception:
            raise Exception("A Dell Mouse")
        if MockFirebaseAdminAuth.throw_create_custom_token_exception:
            return {"email": "testing", "uid": "uid".encode("utf-8")}
        if session_cookie:
            return {"email": session_cookie, "uid": "uid".encode("utf-8")}
        raise Exception("session cookie provided: None")

    @staticmethod
    def get_user_by_email(email):
        if email == "bad":
            raise auth.UserNotFoundError("bad email")

    @staticmethod
    def update_user(uid, email, password):
        pass

    @staticmethod
    def create_custom_token(uid):  # sourcery skip: raise-specific-error
        if MockFirebaseAdminAuth.throw_create_custom_token_exception:
            raise Exception("A Dell Mouse")
        return uid
