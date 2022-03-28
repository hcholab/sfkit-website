from conftest import MockFirebaseAdminAuth

test_create_data = {
    "title": "testtitle",
    "description": "test description",
    "study_information": "hi",
}


def test_validate_data(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.pca.sleep", lambda x: None)

    auth.login()
    client.post("create_study/PCA", data=test_create_data)
    assert client.get("pca/validate_data/testtitle").status_code == 302


def test_start_protocol(client, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.pca.sleep", lambda x: None)

    auth.login()
    client.post("create_study/PCA", data=test_create_data)
    assert client.post("pca/start_protocol/testtitle").status_code == 302
