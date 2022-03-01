from werkzeug import Response
from src.utils import generic_functions


def test_redirect_with_flask(mocker):
    mocker.patch("src.utils.generic_functions.redirect", mock_redirect)
    mocker.patch("src.utils.generic_functions.url_for", mock_url_for)
    mocker.patch("src.utils.generic_functions.flash", mock_flash)
    assert (
        generic_functions.redirect_with_flash(url="test_url", message="test_message")
        == "test_url"
    )


def test_flash():
    response = Response()
    generic_functions.flash(response, "test_message")
    assert "flash=test_message" in response.headers["Set-Cookie"]


def mock_redirect(url):
    return url


def mock_url_for(endpoint):
    return endpoint


def mock_flash(response, message):
    pass
