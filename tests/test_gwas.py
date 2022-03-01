import io
from flask import current_app, g
from copy import deepcopy

import pytest
from src.utils import constants
from src.gwas import run_gwas

from conftest import MockFirebaseAdminAuth

test_create_data = {
    "title": "testtitle",
    "description": "test description",
}


def test_validate_bucket(client, app, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.gwas.GoogleCloudCompute", MockGoogleCloudCompute)
    mocker.patch("src.gwas.GoogleCloudStorage", MockGoogleCloudStorage)
    mocker.patch("src.gwas.GoogleCloudPubsub", MockGoogleCloudPubsub)

    auth.login()
    client.post("create_study", data=test_create_data)
    assert client.get("validate_bucket/testtitle").status_code == 302

    user_parameters = deepcopy(constants.DEFAULT_USER_PARAMETERS)
    user_parameters["GCP_PROJECT"]["value"] = "gcp_project"
    user_parameters["BUCKET_NAME"]["value"] = "bucket_name"
    doc_ref = app.config["DATABASE"].collection("studies").document("testtitle")
    doc_ref.set({"personal_parameters": {"a@a.com": user_parameters}}, merge=True)

    client.get("validate_bucket/testtitle")

    doc_ref.set({"participants": ["blah", "a@a.com"]}, merge=True)
    client.get("validate_bucket/testtitle")


def test_start_gwas(client, app, auth, mocker):
    mocker.patch("src.auth.firebase_auth", MockFirebaseAdminAuth)
    mocker.patch("src.gwas.GoogleCloudCompute", MockGoogleCloudCompute)
    mocker.patch("src.gwas.GoogleCloudStorage", MockGoogleCloudStorage)
    mocker.patch("src.gwas.GoogleCloudPubsub", MockGoogleCloudPubsub)
    mocker.patch("src.gwas.GoogleCloudIAM", MockGoogleCloudIAM)

    auth.login()
    client.post("create_study", data=test_create_data)

    client.post("start_gwas/testtitle")

    MockGoogleCloudStorage.return_value = True
    client.post("start_gwas/testtitle")

    doc_ref = app.config["DATABASE"].collection("studies").document("testtitle")
    doc_ref.set({"status": {"a@a.com": ["not ready"]}}, merge=True)
    client.post("start_gwas/testtitle")

    MockGoogleCloudIAM.return_value = True
    client.post("start_gwas/testtitle", data={"NUM_CPUS": "1", "BOOT_DISK_SIZE": "1"})

    doc_ref.set({"status": {"a@a.com": ["ready"], "b@b.com": ["ready"]}}, merge=True)
    doc_ref.set({"participants": ["b@b.com", "a@a.com"]}, merge=True)
    client.post("start_gwas/testtitle", data={"NUM_CPUS": "1", "BOOT_DISK_SIZE": "1"})

    doc_ref.set(
        {"status": {"a@a.com": ["ready"], "b@b.com": ["not ready"]}}, merge=True
    )
    client.post("start_gwas/testtitle", data={"NUM_CPUS": "1", "BOOT_DISK_SIZE": "1"})


def test_run_gwas(mocker):
    mocker.patch("src.gwas.GoogleCloudPubsub", MockGoogleCloudPubsub)
    mocker.patch("src.gwas.GoogleCloudCompute", MockGoogleCloudCompute)
    mocker.patch("src.gwas.GoogleCloudStorage", MockGoogleCloudStorage)

    run_gwas(
        "role",
        "gcp_project",
        "study title",
        vm_parameters=constants.DEFAULT_USER_PARAMETERS,
    )


def mock_get_status(role, gcp_project, status, study_title):
    return status


def mock_run_gwas(role, gcp_project, study_title, size):
    return True


# class to mock GoogleCloudCompute
class MockGoogleCloudCompute:
    def __init__(self, project):
        pass

    def setup_networking(self, role):
        pass

    def setup_instance(
        self,
        zone,
        instance,
        role,
        vm_parameters=None,
        metadata=None,
        boot_disk_size=None,
        validate=False,
    ):
        pass

    def get_service_account_for_vm(self, zone, instance):
        return "serviceaccount"

    def stop_instance(self, zone, role):
        pass


class MockGoogleCloudStorage:
    return_value = False

    def __init__(self, project):
        pass

    def copy_parameters_to_bucket(self, study_title, role):
        pass

    def upload_to_bucket(self, file, filename):
        pass

    def add_bucket_iam_member(self, bucket_name, role, member):
        pass

    def check_file_exists(self, filename):
        return MockGoogleCloudStorage.return_value


# class to mock GoogleCloudPubsub
class MockGoogleCloudPubsub:
    def __init__(self, project, role, study_title):
        pass

    def create_topic_and_subscribe(self):
        pass

    def delete_topic(self):
        pass

    def add_pub_iam_member(self, role, member):
        pass

    def listen_to_startup_script(self, status):
        return "GWAS Completed!" if status == "finished" else status


# class to mock GoogleCloudIAM
class MockGoogleCloudIAM:
    return_value = False

    def test_permissions(self, project_id):
        return MockGoogleCloudIAM.return_value


class MockFile:
    def __init__(self, filename):
        self.filename = filename
