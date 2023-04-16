# sourcery skip: require-parameter-annotation, require-return-annotation
from io import BytesIO
from conftest import MockFirebaseAdminAuth

test_create_data = {
    "title": "testtitle",
    "description": "test description",
    "study_information": "hi",
    "private_study": "on",
    "demo_study": "on",
}


# def test_upload_file(client, app, mocker):
#     # mock os.makedirs
#     mocker.patch("os.makedirs")
#     # mock file.save
#     mocker.patch("werkzeug.datastructures.FileStorage.save")
#     # mock upload_blob
#     mocker.patch("src.api.upload_blob")

#     doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
#     doc_ref.set({"auth_key": {"study_title": "blah"}})

#     response = client.post(
#         "/upload_file", headers={"Authorization": "auth_key"}, data={"file": (BytesIO(b"some file data"), "test.txt")}
#     )
#     assert response.status_code == 200

#     response = client.post(
#         "/upload_file", headers={"Authorization": "auth_key"}, data={"file": (BytesIO(b"some file data"), b"")}
#     )
#     assert response.status_code == 400

#     response = client.post("/upload_file", data={"file": (BytesIO(b"some file data"), "test.txt")})
#     assert response.status_code == 401


def test_get_doc_ref_dict(client, app):
    doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"study_title": "blah"}})

    response = client.get("/get_doc_ref_dict", headers={"Authorization": "auth_key"})
    assert response.status_code == 200

    response = client.get("/get_doc_ref_dict")
    assert response.status_code == 401


def test_get_username(client, app):
    doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"username": "blah"}})

    response = client.get("/get_username", headers={"Authorization": "auth_key"})
    assert response.status_code == 200

    response = client.get("/get_username")
    assert response.status_code == 401


# def test_update_firestore(client, app, auth, mocker):
#     mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
#     auth.login()
#     client.post("/create_study/MPC-GWAS/website", data=test_create_data)

#     doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
#     doc_ref.set({"auth_key": {"study_title": "testtitle", "username": "a@a.com"}})

#     response = client.get("/update_firestore")
#     assert response.status_code == 401

#     response = client.get(
#         "/update_firestore?msg=update_firestore::status=hello", headers={"Authorization": "auth_key"}
#     )
#     assert response.status_code == 200

#     response = client.get(
#         "/update_firestore?msg=update_firestore::PUBLIC_KEY=pub_key", headers={"Authorization": "auth_key"}
#     )
#     assert response.status_code == 200

#     response = client.get("/update_firestore?msg=update_firestore::NUM_SNPS=57", headers={"Authorization": "auth_key"})
#     assert response.status_code == 200

#     response = client.get(
#         "/update_firestore?msg=update_firestore::blah=very_blah", headers={"Authorization": "auth_key"}
#     )
#     assert response.status_code == 400


def test_create_cp0_fail(client, app, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)

    doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"study_title": "testtitle", "username": "a@a.com"}})

    response = client.get("/create_cp0")
    assert response.status_code == 401

    response = client.get("/create_cp0", headers={"Authorization": "auth_key"})
    assert response.status_code == 400


def test_create_cp0_success(client, app, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    # patch setup_gcp
    mocker.patch("src.api.setup_gcp", return_value=None)
    auth.login()
    client.post("/create_study/MPC-GWAS/website", data=test_create_data)

    response = client.get("/create_cp0", headers={"Authorization": "auth_key"})

    doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"study_title": "testtitle", "username": "a@a.com"}})

    response = client.get("/create_cp0", headers={"Authorization": "auth_key"})
    assert response.status_code == 200
