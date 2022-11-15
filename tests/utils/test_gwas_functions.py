from conftest import MockFirebaseAdminAuth
from src.utils import gwas_functions

test_create_data = {
    "title": "testtitle",
    "description": "test description",
    "study_information": "hi",
    "private_study": "on",
}

test_create_data2 = {
    "title": "testtitle2",
    "description": "test description2",
    "study_information": "hi",
    "private_study": "on",
}

test_doc_ref_dict = {
    "participants": ["Broad", "a@a.com"],
    "parameters": {"NUM_SNPS": {"value": "10"}},
    "personal_parameters": {"Broad": {"NUM_INDS": {"value": "10"}}, "a@a.com": {"NUM_INDS": {"value": "10"}}},
}


# def test_valid_study_title(client, app, auth, mocker):
#     setup_mocking(mocker)
#     with app.app_context():
#         assert gwas_functions.valid_study_title("testtitle", "MPCGWAS", "user")[0] == True
#         assert gwas_functions.valid_study_title("test_title", "MPCGWAS", "user")[0] == False

#         auth.login()
#         client.post("create_study/MPCGWAS/website", data=test_create_data)
#         client.post("create_study/MPCGWAS/website", data=test_create_data2)

#         assert gwas_functions.valid_study_title("testtitle2", "MPCGWAS", "user")[0] == False


def test_create_instance_name():
    assert gwas_functions.create_instance_name("testtitle", "1") == "testtitle-secure-gwas1"


# def test_data_has_valid_size():
#     assert gwas_functions.data_has_valid_size(20000, test_doc_ref_dict, 1) == True
#     assert gwas_functions.data_has_valid_size(2000, test_doc_ref_dict, 1) == False
#     assert gwas_functions.data_has_valid_size(200000, test_doc_ref_dict, 1) == False


# def test_data_has_valid_files():
#     assert gwas_functions.data_has_valid_files("g.bin m.bin p.bin other_shared_key.bin pos.txt") == True
#     assert gwas_functions.data_has_valid_files("one two three") == False


def setup_mocking(mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.utils.gwas_functions.redirect", mock_redirect)
    mocker.patch("src.utils.gwas_functions.url_for", mock_url_for)
    mocker.patch("src.utils.gwas_functions.redirect_with_flash", mock_redirect_with_flash)


def mock_redirect_with_flash(url="", location: str = "", message: str = "", error: str = ""):
    return location


def mock_redirect(url):
    return url


def mock_url_for(endpoint, study_title="", study_type=""):
    return endpoint
