from typing import Callable, Generator
from unittest.mock import MagicMock

from flask import Flask
from flask.testing import FlaskClient
from pytest_mock import MockerFixture
from werkzeug import Request
from werkzeug.test import EnvironBuilder

from src.utils.api_functions import (
    delete_instance,
    process_parameter,
    process_status,
    process_task,
    stop_instance,
    update_parameter,
    update_tasks,
    verify_authorization_header,
)


def test_process_status(mocker: Callable[..., Generator[MockerFixture, None, None]]) -> None:
    db = MagicMock()
    username = "test_user"
    study_title = "test_study"
    parameter = "status=Finished protocol"
    doc_ref = MagicMock()
    doc_ref_dict = {
        "setup_configuration": "website",
        "personal_parameters": {"test_user": {"DELETE_VM": {"value": "Yes"}}},
    }
    gcp_project = "test_project"
    role = "test_role"

    mocker.patch("src.utils.api_functions.delete_instance")
    mocker.patch("src.utils.api_functions.stop_instance")

    process_status(db, username, study_title, parameter, doc_ref, doc_ref_dict, gcp_project, role)

    doc_ref_dict = {
        "setup_configuration": "user",
        "personal_parameters": {"test_user": {"DELETE_VM": {"value": "Yes"}}},
    }
    process_status(db, username, study_title, parameter, doc_ref, doc_ref_dict, gcp_project, role)

    doc_ref_dict = {
        "setup_configuration": "website",
        "personal_parameters": {"test_user": {"DELETE_VM": {"value": "No"}}},
    }
    process_status(db, username, study_title, parameter, doc_ref, doc_ref_dict, gcp_project, role)


def test_process_task(mocker: Callable[..., Generator[MockerFixture, None, None]]) -> None:
    db = MagicMock()
    username = "test_user"
    parameter = "task=Finished protocol"
    doc_ref = MagicMock()

    mocker.patch("src.utils.api_functions.update_tasks")

    process_task(db, username, parameter, doc_ref)

    mocker.patch("src.utils.api_functions.time.sleep")
    mocker.patch("src.utils.api_functions.update_tasks", side_effect=Exception("test"))
    process_task(db, username, parameter, doc_ref)


def test_process_parameter(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    db = MagicMock()
    username = "test_user"
    parameter = "parameter=Finished protocol"
    doc_ref = MagicMock()

    mocker.patch("src.utils.api_functions.update_parameter")
    process_parameter(db, username, parameter, doc_ref)

    mocker.patch("src.utils.api_functions.update_parameter", return_value=False)
    process_parameter(db, username, parameter, doc_ref)

    mocker.patch("src.utils.api_functions.time.sleep")
    mocker.patch("src.utils.api_functions.update_parameter", side_effect=Exception("test"))
    process_parameter(db, username, parameter, doc_ref)


def test_update_parameter(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    transaction = MagicMock()
    username = "test_user"
    parameter = "test_parameter=test_value"
    doc_ref = MagicMock()
    doc_ref.get.return_value.to_dict.return_value = {
        "personal_parameters": {"test_user": {"test_parameter": {"value": "old_value"}}},
        "parameters": {"test_parameter": {"value": "old_value"}},
    }

    # test updating personal parameter
    result = update_parameter(transaction, username, parameter, doc_ref)
    assert result is True
    transaction.update.assert_called_once

    # test updating global parameter
    doc_ref.get.return_value.to_dict.return_value = {
        "personal_parameters": {"test_user": {"bad": {"value": "old_value"}}},
        "parameters": {"test_parameter": {"value": "old_value"}},
    }
    result = update_parameter(transaction, username, parameter, doc_ref)

    doc_ref.get.return_value.to_dict.return_value = {
        "personal_parameters": {"test_user": {"bad": {"value": "old_value"}}},
        "parameters": {"bad": {"value": "old_value"}},
    }
    assert update_parameter(transaction, username, parameter, doc_ref) is False


def test_update_tasks(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    transaction = MagicMock()
    username = "test_user"
    task = "test_task"
    doc_ref = MagicMock()
    doc_ref.get.return_value.to_dict.return_value = {"tasks": {username: []}}

    # test adding a new task
    update_tasks(transaction, doc_ref, username, task)
    transaction.update.assert_called_once

    # test adding a duplicate task
    update_tasks(transaction, doc_ref, username, task)
    transaction.update.assert_called_once


def test_delete_instance(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    study_title = "test_study"
    doc_ref_dict = {"title": "test_title"}
    gcp_project = "test_project"
    role = "test_role"

    mocker.patch("src.utils.api_functions.GoogleCloudCompute")
    mocker.patch("src.utils.api_functions.create_instance_name")
    delete_instance(study_title, doc_ref_dict, gcp_project, role)


def test_stop_instance(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    study_title = "test_study"
    doc_ref_dict = {"title": "test_title"}
    gcp_project = "test_project"
    role = "test_role"

    mocker.patch("src.utils.api_functions.GoogleCloudCompute")
    mocker.patch("src.utils.api_functions.create_instance_name")
    stop_instance(study_title, doc_ref_dict, gcp_project, role)


def test_verify_authorization_header(
    client: FlaskClient, app: Flask, mocker: Callable[..., Generator[MockerFixture, None, None]]
):
    # sourcery skip: extract-duplicate-method

    db = app.config["DATABASE"]
    doc_ref = db.collection("users").document("auth_keys")
    doc_ref.set({"auth_key": {"username": "a@a.com", "study_title": "testtitle"}})

    with app.app_context():
        headers = {"Content-Type": "application/json", "Authorization": "Bearer mytoken"}
        environ = EnvironBuilder(headers=headers).get_environ()  # type: ignore
        result = verify_authorization_header(Request(environ))
        assert result == ""

        headers = {"Content-Type": "application/json", "Authorization": "auth_key"}
        environ = EnvironBuilder(headers=headers).get_environ()  # type: ignore
        result = verify_authorization_header(Request(environ))
        assert result == "auth_key"
