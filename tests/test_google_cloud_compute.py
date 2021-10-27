from src import constants
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
import random
import pytest


def test_setup_networking(mocker):
    mocker.patch("time.sleep", lambda x: None)
    mocker.patch(
        "src.utils.google_cloud.google_cloud_compute.googleapi",
        MockMakeMockCompute,
    )
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    for _ in range(20):
        try:
            google_cloud_compute.setup_networking("0")
        except Exception as e:
            if str(e) != "fake error" and "RetryError" not in str(e):
                raise


# again but with different project
def test_setup_networking_different_project(mocker):
    mocker.patch("time.sleep", lambda x: None)
    mocker.patch(
        "src.utils.google_cloud.google_cloud_compute.googleapi",
        MockMakeMockCompute,
    )
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv2")
    for _ in range(20):
        try:
            google_cloud_compute.setup_networking("0")
        except Exception as e:
            if str(e) != "fake error" and "RetryError" not in str(e):
                raise


def test_setup_instance(mocker):
    mocker.patch("time.sleep", lambda x: None)
    mocker.patch(
        "src.utils.google_cloud.google_cloud_compute.googleapi",
        MockMakeMockCompute,
    )
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")

    for _ in range(10):
        try:
            google_cloud_compute.setup_instance(
                zone="zone", name=constants.NETWORK_NAME, role="role"
            )
        except Exception as e:
            if str(e) != "fake error" and "RetryError" not in str(e):
                raise


def test_stop_instance(mocker):
    mocker.patch("time.sleep", lambda x: None)
    mocker.patch(
        "src.utils.google_cloud.google_cloud_compute.googleapi",
        MockMakeMockCompute,
    )
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")

    for _ in range(10):
        try:
            google_cloud_compute.stop_instance(zone="zone", instance="name")
        except Exception as e:
            if str(e) != "fake error" and "RetryError" not in str(e):
                raise


def test_get_service_account_for_vm(mocker):
    mocker.patch("time.sleep", lambda x: None)
    mocker.patch(
        "src.utils.google_cloud.google_cloud_compute.googleapi",
        MockMakeMockCompute,
    )
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.get_service_account_for_vm(zone="zone", instance="name")


class MockMakeMockCompute:
    def __init__(self):
        pass

    def build(api, version):
        return MockCompute()


class MockCompute:
    def __init__(self):
        pass

    def networks(self):
        return MockInsertable()

    def subnetworks(self):
        return MockInsertable()

    def firewalls(self):
        return MockInsertable()

    def instances(self):
        return MockInsertable()

    def images(self):
        return MockInsertable()

    def globalOperations(self):
        return MockOperations()

    def regionOperations(self):
        return MockOperations()

    def zoneOperations(self):
        return MockOperations()


class MockOperations:
    def __init__(self):
        pass

    def get(self, project, operation, region=None, zone=None):
        return MockExecutable()


class MockInsertable:
    def __init__(self):
        pass

    def list(self, project=None, region=None, zone=None):
        return MockExecutable()

    def insert(self, project=None, zone=None, region=None, body=None):
        return MockExecutable()

    def get(self, project=None, network=None, zone=None, instance=None):
        return MockExecutable()

    def delete(
        self, project=None, zone=None, region=None, subnetwork=None, instance=None
    ):
        return MockExecutable()

    def stop(self, project, zone, instance):
        return MockExecutable()

    def addPeering(self, project, network, body):
        return MockExecutable()

    def removePeering(self, project, network, body):
        return MockExecutable()

    def getFromFamily(self, project, family):
        return MockExecutable()


class MockExecutable:
    def __init__(self):
        pass

    def execute(self):
        networkName1 = "1" if random.random() < 0.5 else constants.NETWORK_NAME
        networkName2 = "1" if random.random() < 0.5 else constants.NETWORK_NAME
        status = "RUNNING" if random.random() < 0.5 else "DONE"
        creationTimestamp = "z" if random.random() < 0.5 else "2020-04-01T00:00:00Z"
        project = random.choice(["broad-cho-priv1", "broad-cho-priv2"])
        res = {
            "items": [
                {
                    "name": networkName1,
                    "creationTimestamp": creationTimestamp,
                    "selfLink": "hi",
                    "networkInterfaces": [{"subnetwork": "hi"}],
                },
                {
                    "name": networkName2,
                    "creationTimestamp": creationTimestamp,
                    "selfLink": "hi",
                    "networkInterfaces": [{"subnetwork": "hi"}],
                },
            ],
            "status": status,
            "name": "operation",
            "selfLink": "selfLink",
            "networkInterfaces": [{"accessConfigs": [{"natIP": "hi"}]}],
            "peerings": [{"name": f"peering-{project}"}],
            "serviceAccounts": [{"email": "hi"}],
        }
        if random.random() < 0.5:
            res["error"] = "fake error"
        return res
