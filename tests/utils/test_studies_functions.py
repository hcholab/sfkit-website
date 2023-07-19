import os
import tempfile
import zipfile
from typing import Callable, Generator, Literal
from unittest.mock import MagicMock

import pytest
from flask import Flask
from google.cloud.firestore_v1.document import DocumentReference
from pytest_mock import MockerFixture
from python_http_client.exceptions import HTTPError

from src.utils import studies_functions as sf
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from src.utils.studies_functions import (
    add_file_to_zip,
    check_conditions,
    clean_study_title,
    is_study_title_unique,
    update_status_and_start_setup,
)


def test_email(
    app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]
):  # sourcery skip: extract-duplicate-method
    with app.test_request_context():
        sendgrid_mock = mocker.patch("src.utils.studies_functions.SendGridAPIClient")
        sendgrid_send_mock = sendgrid_mock.return_value.send

        # Test successful email sending
        sf.email("a@a.com", "b@b.com", "", "study_title")
        sendgrid_send_mock.assert_called_once()

        sendgrid_send_mock.reset_mock()

        sf.email("a@a.com", "b@b.com", "invitation_message", "study_title")
        sendgrid_send_mock.assert_called_once()

        sendgrid_send_mock.reset_mock()

        # Test email sending failure due to HTTPError
        sendgrid_send_mock.side_effect = HTTPError(
            400, "Not Found", "The requested resource was not found.", {"Content-Type": "text/plain"}
        )

        status_code = sf.email("a@a.com", "b@b.com", "invitation_message", "study_title")
        assert status_code == 400


def test_clean_study_title():
    assert clean_study_title("123abc-!@#$%^&*() def") == "abc-def"
    assert clean_study_title("12345") == ""
    assert clean_study_title("!@#$%") == ""
    assert clean_study_title("Sample Study Title") == "samplestudytitle"


def test_is_study_title_unique():
    db = MagicMock()
    db.collection().where().limit().stream.return_value = iter([])
    assert is_study_title_unique("unique_title", db) is True

    db.collection().where().limit().stream.return_value = iter(["not_unique_title"])
    assert is_study_title_unique("not_unique_title", db) is False


def test_valid_study_title(app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    with app.test_request_context():
        mocker.patch("src.utils.studies_functions.clean_study_title", return_value="testtitle")
        mocker.patch("src.utils.studies_functions.is_study_title_unique", return_value=True)
        mocker.patch("src.utils.studies_functions.url_for", return_value="/studies/parameters/testtitle")
        redirect_with_flash_mock = mocker.patch("src.utils.studies_functions.redirect_with_flash")

        cleaned_study_title, response = sf.valid_study_title("testtitle", "MPC-GWAS", "user")
        assert cleaned_study_title == "testtitle"

        mocker.patch("src.utils.studies_functions.clean_study_title", return_value="")
        mocker.patch("src.utils.studies_functions.is_study_title_unique", return_value=False)

        cleaned_study_title, response = sf.valid_study_title("test_title", "MPC-GWAS", "user")
        assert cleaned_study_title == ""
        assert redirect_with_flash_mock.called


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/path/to/data/", "/path/to/data"),
        ("/path/to/data", "/path/to/data"),
        ("", ""),
    ],
)
def test_sanitize_path(path: Literal["/path/to/data/", "/path/to/data", ""], expected: Literal["/path/to/data", ""]):
    assert sf.sanitize_path(path) == expected


def test_is_developer(app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    with app.test_request_context():
        mocker.patch("src.utils.studies_functions.os.environ", {"FLASK_DEBUG": "development"})
        mocker.patch("src.utils.studies_functions.constants.DEVELOPER_USER_ID", "developer_id")
        mocker.patch("src.utils.studies_functions.g", user={"id": "developer_id"})
        assert sf.is_developer() is True

        mocker.patch("src.utils.studies_functions.g", user={"id": "non_developer_id"})
        assert sf.is_developer() is False


def test_is_participant(app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mock_study = {"participants": ["participant_id"]}

    with app.test_request_context():
        mocker.patch("src.utils.studies_functions.g", user={"id": "participant_id"})
        assert sf.is_participant(mock_study) is True

        mocker.patch("src.utils.studies_functions.g", user={"id": "non_participant_id"})
        assert sf.is_participant(mock_study) is False


def test_add_file_to_zip():
    # Create a temporary file with some content
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"Test content")

    # Create a temporary ZIP file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip_file:
        # Open the temporary ZIP file with zipfile.ZipFile
        with zipfile.ZipFile(temp_zip_file.name, "w") as zip_file:
            # Call the add_file_to_zip function
            add_file_to_zip(zip_file, temp_file.name)

        # Open the temporary ZIP file again to verify its contents
        with zipfile.ZipFile(temp_zip_file.name, "r") as zip_file:
            file_list = zip_file.namelist()
            assert len(file_list) == 1
            assert file_list[0] == os.path.basename(temp_file.name)
            assert zip_file.read(file_list[0]) == b"Test content"

    # Clean up temporary files
    os.remove(temp_file.name)
    os.remove(temp_zip_file.name)


@pytest.fixture
def doc_ref_mock():
    doc_ref = MagicMock(spec=DocumentReference)
    doc_ref.get.return_value.to_dict.return_value = {
        "title": "test_study",
        "participants": ["user1", "user2"],
        "demo": False,
        "personal_parameters": {
            "user1": {
                "GCP_PROJECT": {"value": "project1"},
                "DATA_PATH": {"value": "/data/path"},
                "GENO_BINARY_FILE_PREFIX": {"value": "geno_prefix"},
                "PORTS": {"value": "8000,8020"},
                "AUTH_KEY": {"value": "auth_key"},
                "NUM_CPUS": {"value": "2"},
                "BOOT_DISK_SIZE": {"value": "10"},
            },
            "user2": {
                "GCP_PROJECT": {"value": "project2"},
                "DATA_PATH": {"value": "/data/path"},
                "GENO_BINARY_FILE_PREFIX": {"value": "geno_prefix"},
                "PORTS": {"value": "8200,8220"},
                "AUTH_KEY": {"value": "auth_key"},
                "NUM_CPUS": {"value": "2"},
                "BOOT_DISK_SIZE": {"value": "10"},
            },
        },
        "status": {"user1": "", "user2": ""},
    }
    return doc_ref


def test_generate_ports(doc_ref_mock: MagicMock):
    def helper(doc_ref_mock, arg1, arg2):
        sf.generate_ports(doc_ref_mock, arg1)
        doc_ref_mock.get.assert_called_once()

    helper(doc_ref_mock, "0", "")
    doc_ref_mock.reset_mock()
    helper(doc_ref_mock, "1", "8200,8220")


def test_setup_gcp(doc_ref_mock: MagicMock, mocker: Callable[..., Generator[MockerFixture, None, None]]):
    generate_ports_mock = mocker.patch("src.utils.studies_functions.generate_ports")
    gcloud_compute_mock = MagicMock(spec=GoogleCloudCompute)
    gcloud_compute_mock_class_mock = mocker.patch(
        "src.utils.studies_functions.GoogleCloudCompute", return_value=gcloud_compute_mock
    )
    mocker.patch("src.utils.studies_functions.sanitize_path", return_value="/data/path")
    mocker.patch("src.utils.studies_functions.format_instance_name", return_value="instance_name")
    logger_error_mock = mocker.patch("src.utils.studies_functions.logger.error")

    # Test successful execution of setup_gcp
    sf.setup_gcp(doc_ref_mock, "0")

    generate_ports_mock.assert_called_once_with(doc_ref_mock, "0")
    gcloud_compute_mock_class_mock.assert_called_once_with("test_study", "project1")
    gcloud_compute_mock.setup_networking.assert_called_once()

    # Test execution with exception raised
    gcloud_compute_mock.reset_mock()
    gcloud_compute_mock.setup_networking.side_effect = Exception("GCP setup error")

    sf.setup_gcp(doc_ref_mock, "0")

    gcloud_compute_mock.setup_networking.assert_called_once()
    logger_error_mock.assert_called_once_with("An error occurred during GCP setup: GCP setup error")


def test_update_status_and_start_setup(app, mocker):
    with app.test_request_context():
        # Mock external functions
        mocker.patch("src.utils.studies_functions.setup_gcp", lambda *args, **kwargs: None)
        mocker.patch("src.utils.studies_functions.make_auth_key")
        mocker.patch("src.utils.studies_functions.Thread.start")
        mocker.patch("src.utils.studies_functions.time.sleep")

        # Test input
        doc_ref = MagicMock()
        doc_ref_dict = {
            "participants": ["Broad", "user1", "user2"],
            "status": {
                "Broad": "ready to begin sfkit",
                "user1": "ready to begin sfkit",
                "user2": "ready to begin sfkit",
            },
        }
        user_id = "user1"

        update_status_and_start_setup(doc_ref, doc_ref_dict, user_id)


def test_check_conditions(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mock_iam = MagicMock()
    mock_iam.test_permissions.return_value = False
    mocker.patch("src.utils.studies_functions.GoogleCloudIAM", return_value=mock_iam)

    case = {
        "doc_ref_dict": {
            "participants": ["Broad", "a@a.com"],
            "personal_parameters": {
                "a@a.com": {
                    "NUM_INDS": {"value": ""},
                    "GCP_PROJECT": {"value": ""},
                    "DATA_PATH": {"value": ""},
                },
            },
            "demo": False,
        },
        "user_id": "a@a.com",
    }

    assert "Non-demo studies" in check_conditions(**case)

    case["doc_ref_dict"]["participants"].append("b@b.com")
    assert "You have not set" in check_conditions(**case)

    case["doc_ref_dict"]["personal_parameters"]["a@a.com"]["NUM_INDS"]["value"] = "1"
    assert "Your GCP project" in check_conditions(**case)

    case["doc_ref_dict"]["personal_parameters"]["a@a.com"]["GCP_PROJECT"]["value"] = "broad-cho-priv1"
    assert "This project ID" in check_conditions(**case)

    case["doc_ref_dict"]["personal_parameters"]["a@a.com"]["GCP_PROJECT"]["value"] = "TEST_GCP_PROJECT"
    assert "Your data path" in check_conditions(**case)

    case["doc_ref_dict"]["personal_parameters"]["a@a.com"]["DATA_PATH"]["value"] = "/data/path"
    assert "You have not given" in check_conditions(**case)

    mock_iam.test_permissions.return_value = True
    mocker.patch("src.utils.studies_functions.GoogleCloudIAM", return_value=mock_iam)
    assert check_conditions(**case) == ""
