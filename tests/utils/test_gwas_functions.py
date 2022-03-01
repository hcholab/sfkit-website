from conftest import MockFirebaseAdminAuth
from src.utils import gwas_functions


test_create_data = {
    "title": "testtitle",
    "description": "test description",
}

test_create_data2 = {
    "title": "testtitle2",
    "description": "test description2",
}

test_doc_ref_dict = {
    "participants": ["a@a.com"],
    "parameters": {"NUM_SNPS": {"value": "10"}},
    "personal_parameters": {"a@a.com": {"NUM_INDS": {"value": "10"}}},
}


def test_valid_study_title(client, app, auth, mocker):
    setup_mocking(mocker)
    with app.app_context():
        assert gwas_functions.valid_study_title("testtitle")[0] == True
        assert gwas_functions.valid_study_title("test_title")[0] == False

        auth.login()
        client.post("create_study", data=test_create_data)
        client.post("create_study", data=test_create_data2)

        assert gwas_functions.valid_study_title("testtitle2")[0] == False


def test_create_instance_name():
    assert (
        gwas_functions.create_instance_name("testtitle", "1")
        == "testtitle-secure-gwas1"
    )


def test_data_is_valid():
    assert gwas_functions.data_is_valid(20000, test_doc_ref_dict, 1) == True
    assert gwas_functions.data_is_valid(2000, test_doc_ref_dict, 1) == False
    assert gwas_functions.data_is_valid(200000, test_doc_ref_dict, 1) == False


def setup_mocking(mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.utils.gwas_functions.redirect", mock_redirect)
    mocker.patch("src.utils.gwas_functions.url_for", mock_url_for)
    mocker.patch(
        "src.utils.gwas_functions.redirect_with_flash", mock_redirect_with_flash
    )


def mock_redirect_with_flash(location, message):
    return location


def mock_redirect(url):
    return url


def mock_url_for(endpoint):
    return endpoint
