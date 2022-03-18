from conftest import MockFirebaseAdminAuth
from src.utils import generic_functions
from werkzeug import Response


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


def test_get_notifications(app, auth, mocker, client):
    setup_mocking_and_doc_ref(app, auth, mocker)

    with app.app_context():
        client.get("/")  # this is needed to set the g.user
        assert "hi" in generic_functions.get_notifications()


def test_remove_notification(app, auth, mocker, client):
    doc_ref = setup_mocking_and_doc_ref(app, auth, mocker)

    with app.app_context():
        client.get("/")  # this is needed to set the g.user
        generic_functions.remove_notification("hi")
        assert "hi" not in doc_ref.get().to_dict()["notifications"]


def test_add_notification(app, auth, mocker, client):
    doc_ref = setup_mocking_and_doc_ref(app, auth, mocker)

    with app.app_context():
        client.get("/")  # this is needed to set the g.user
        generic_functions.add_notification("goodbye", "a@a.com")
        assert "goodbye" in doc_ref.get().to_dict()["notifications"]


def setup_mocking_and_doc_ref(app, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    auth.login()
    doc_ref = app.config["DATABASE"].collection("users").document("a@a.com")
    doc_ref.set({"notifications": ["hi"]})
    return doc_ref


def mock_redirect(url):
    return url


def mock_url_for(endpoint):
    return endpoint


def mock_flash(response, message):
    pass
