from typing import Callable, Generator

import pytest
from conftest import MockFirebaseAdminAuth
from flask import Flask
from pytest_mock import MockerFixture
from requests.models import Response as RequestsResponse
from werkzeug import Response

from src.utils import auth_functions


def test_create_user(app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    with app.app_context():
        mocker.patch("src.utils.auth_functions.firebase_auth", MockFirebaseAdminAuth)
        mocker.patch(
            "src.utils.auth_functions.sign_in_with_email_and_password",
            mock_sign_in_with_email_and_password,
        )
        mocker.patch("src.utils.auth_functions.redirect", mock_redirect)
        mocker.patch("src.utils.auth_functions.url_for", mock_url_for)

        response = auth_functions.create_user("test_id", "test_name", "/test-redirect-url")
        assert "session=test_token" in response.headers["Set-Cookie"]

        response = auth_functions.create_user(name="anonymous_user")
        assert "session=test_token" in response.headers["Set-Cookie"]

        response = auth_functions.create_user(name="UserNotFound")


def test_update_user(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.utils.auth_functions.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch(
        "src.utils.auth_functions.sign_in_with_email_and_password",
        mock_sign_in_with_email_and_password,
    )
    mocker.patch("src.utils.auth_functions.redirect", mock_redirect)
    mocker.patch("src.utils.auth_functions.url_for", mock_url_for)

    response = auth_functions.update_user("a@a.com", "test_password")
    assert "session=test_token" in response.headers["Set-Cookie"]


def test_sign_in_with_email_and_password(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.utils.auth_functions.get_firebase_api_key", return_value="")
    mocker.patch("src.utils.auth_functions.post", mock_post)
    mocker.patch("src.utils.auth_functions.raise_detailed_error", mock_raise_detailed_error)

    auth_functions.sign_in_with_email_and_password("email", "password")


def test_raise_detailed_error():
    response = RequestsResponse()
    response.status_code = 200
    auth_functions.raise_detailed_error(response)
    response.status_code = 404
    with pytest.raises(Exception):
        auth_functions.raise_detailed_error(response)


def mock_sign_in_with_email_and_password(email, password):
    return {"idToken": "test_token"}


def mock_redirect(url):
    return Response()


def mock_url_for(endpoint):
    return endpoint


def mock_post(request_ref, headers, data):
    return MockResponse()


def mock_raise_detailed_error(request_object):
    pass


class MockResponse:
    def json(self):
        return {"idToken": "test_token"}
