# sourcery skip: require-parameter-annotation, require-return-annotation
from io import BytesIO
from typing import Callable, Generator

from conftest import AuthActions, MockFirebaseAdminAuth
from flask import Flask
from flask.testing import FlaskClient
from pytest_mock import MockerFixture

test_create_data = {
    "title": "testtitle",
    "description": "test description",
    "study_information": "hi",
    "private_study": "on",
    "demo_study": "on",
}


def test_upload_file(client: FlaskClient, app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.api.verify_authorization_header", return_value="auth_key")
    mocker.patch("src.api.upload_blob_from_file")

    # Prepare test data
    files = [
        ("test_file.txt", "result.txt"),
        ("manhattan.png", "manhattan.png"),
        ("pca_plot.png", "pca_plot.png"),
        ("pos.txt", "pos.txt"),
    ]

    headers = {"Authorization": "auth_key"}

    db = app.config["DATABASE"]
    doc_ref = db.collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"username": "a@a.com", "study_title": "testtitle"}})

    db.collection("studies").document("testtitle").set({"participants": ["a@a.com"]}, merge=True)

    for file_name, expected_file_name in files:
        data = {"file": (BytesIO(b"test_file_data"), file_name)}
        response = client.post("/upload_file", data=data, headers=headers, content_type="multipart/form-data")
        assert response.status_code == 200

    # Test the case when no file is provided
    response = client.post("/upload_file", headers=headers, content_type="multipart/form-data")
    assert response.status_code == 400

    mocker.patch("src.api.verify_authorization_header", return_value="")
    client.post("/upload_file")


def test_get_doc_ref_dict(client: FlaskClient, app: Flask):
    doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"study_title": "blah"}})

    response = client.get("/get_doc_ref_dict", headers={"Authorization": "auth_key"})
    assert response.status_code == 200

    response = client.get("/get_doc_ref_dict")
    assert response.status_code == 401


def test_get_username(client: FlaskClient, app: Flask):
    doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"username": "blah"}})

    response = client.get("/get_username", headers={"Authorization": "auth_key"})
    assert response.status_code == 200

    response = client.get("/get_username")
    assert response.status_code == 401


def test_update_firestore(
    client: FlaskClient, app: Flask, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.api.verify_authorization_header", return_value="auth_key")
    mocker.patch("src.api.process_status")
    mocker.patch("src.api.process_task")
    mocker.patch("src.api.process_parameter")

    db = app.config["DATABASE"]
    doc_ref = db.collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"username": "a@a.com", "study_title": "testtitle"}})

    auth.login()
    client.post("/create_study/MPC-GWAS/website", data=test_create_data)

    # Test process_status
    response = client.get("/update_firestore?msg=update::statusnew_status", headers={"Authorization": "auth_key"})
    assert response.status_code == 200

    # Test process_task
    response = client.get("/update_firestore?msg=update::tasknew_task", headers={"Authorization": "auth_key"})
    assert response.status_code == 200

    # Test process_parameter
    response = client.get(
        "/update_firestore?msg=update::parameternew_parameter", headers={"Authorization": "auth_key"}
    )
    assert response.status_code == 200

    # Test unauthorized request
    mocker.patch("src.api.verify_authorization_header", return_value="")
    response = client.get("/update_firestore?msg=status::new_status")
    assert response.status_code == 401


def test_create_cp0(
    client: FlaskClient, app: Flask, auth: AuthActions, mocker: Callable[..., Generator[MockerFixture, None, None]]
):  # sourcery skip: extract-duplicate-method
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.api.setup_gcp", return_value=None)
    mocker.patch("src.api.verify_authorization_header", return_value="auth_key")

    auth.login()
    client.post("/create_study/MPC-GWAS/website", data=test_create_data)

    doc_ref = app.config["DATABASE"].collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"study_title": "bad", "username": "a@a.com"}})

    response = client.get("/create_cp0", headers={"Authorization": "auth_key"})
    assert response.status_code == 400

    doc_ref.set({"auth_key": {"study_title": "testtitle", "username": "a@a.com"}})
    response = client.get("/create_cp0", headers={"Authorization": "auth_key"})
    assert response.status_code == 200

    mocker.patch("src.api.verify_authorization_header", return_value="")
    response = client.get("/create_cp0")
    assert response.status_code == 401
