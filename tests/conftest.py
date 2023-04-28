import logging
from typing import Callable, Generator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from mockfirestore import MockFirestore
from pytest_mock import MockerFixture

from src import create_app
from src.utils.logging import setup_logging

logger = setup_logging(__name__)
logger.setLevel(logging.DEBUG)


@pytest.fixture
def app(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.firestore.Client", MockFirestore)
    mocker.patch("src.firebase_admin.initialize_app", return_value=None)
    return create_app()


@pytest.fixture
def client(app: Flask):
    return app.test_client()


@pytest.fixture
def auth(client: FlaskClient, mocker: Callable[..., Generator[MockerFixture, None, None]], app: Flask):
    return AuthActions(client, mocker, app)


class AuthActions:
    """
    A helper class for handling user authentication actions during testing.
    """

    def __init__(self, client, mocker, app):
        self._client = client
        self._mocker = mocker
        self._app = app

    def register(self, email="a@a.com", password="a", password_check="a"):
        """
        Register a user for testing purposes.
        """
        self.login(email, password)

    def login(self, email="a@a.com", password="a"):
        """
        Log in a user for testing purposes.
        """
        self._client.set_cookie(key="session", value=email, path="/", domain="localhost")

    def logout(self):
        """
        Log out a user for testing purposes.
        """
        self._client.delete_cookie(key="session", path="/", domain="localhost")


class MockFirebaseAdminAuth:
    class UserNotFoundError(Exception):
        pass

    class EmailExistsError(Exception):
        pass

    class InvalidSessionError(Exception):
        pass

    throw_verify_session_cookie_exception = False
    throw_create_custom_token_exception = False

    @staticmethod
    def create_user(email, password, uid=None):
        if not email:
            raise MockFirebaseAdminAuth.InvalidSessionError()
        elif "duplicate" in email:
            raise MockFirebaseAdminAuth.EmailExistsError("EMAIL_EXISTS")

    @staticmethod
    def create_session_cookie(user_token, expires_in=None):
        return user_token

    @staticmethod
    def verify_session_cookie(session_cookie, check_revoked=True):
        # sourcery skip: raise-specific-error
        if MockFirebaseAdminAuth.throw_verify_session_cookie_exception:
            raise MockFirebaseAdminAuth.InvalidSessionError()
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
        if "UserNotFound" in email:
            raise MockFirebaseAdminAuth.UserNotFoundError("UserNotFound")

    @staticmethod
    def create_custom_token(uid):
        if MockFirebaseAdminAuth.throw_create_custom_token_exception:
            raise MockFirebaseAdminAuth.InvalidSessionError()
        return uid
