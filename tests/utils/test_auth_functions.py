import pytest
from conftest import MockFirebaseAdminAuth
from requests.models import Response as RequestsResponse
from src.utils import auth_functions
from werkzeug import Response


def test_update_user(mocker):
    mocker.patch("src.utils.auth_functions.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch(
        "src.utils.auth_functions.sign_in_with_email_and_password",
        mock_sign_in_with_email_and_password,
    )
    mocker.patch("src.utils.auth_functions.redirect", mock_redirect)
    mocker.patch("src.utils.auth_functions.url_for", mock_url_for)

    response = auth_functions.update_user("a@a.com", "test_password")
    assert "session=test_token" in response.headers["Set-Cookie"]


def test_sign_in_with_email_and_password(mocker):
    mocker.patch("src.utils.auth_functions.post", mock_post)
    mocker.patch("src.utils.auth_functions.raise_detailed_error", mock_raise_detailed_error)

    auth_functions.sign_in_with_email_and_password("email", "password")


def test_raise_detailed_error():
    r = RequestsResponse()
    r.status_code = 200
    auth_functions.raise_detailed_error(r)
    r.status_code = 404
    with pytest.raises(Exception):
        auth_functions.raise_detailed_error(r)


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
