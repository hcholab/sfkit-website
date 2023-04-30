from typing import Callable, Generator
import pytest
from pytest_mock import MockerFixture
from src.utils import constants
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute, create_instance_name

patch_prefix = "src.utils.google_cloud.google_cloud_compute.GoogleCloudCompute"


def test_setup_networking(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.create_network_if_it_does_not_already_exist", return_value=None)
    mocker.patch(f"{patch_prefix}.remove_conflicting_peerings", return_value=None)
    mocker.patch(f"{patch_prefix}.remove_conflicting_subnets", return_value=None)
    mocker.patch(f"{patch_prefix}.create_subnet", return_value=None)
    mocker.patch(f"{patch_prefix}.create_peerings", return_value=None)

    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.setup_networking(
        {
            "personal_parameters": {"Broad": {"GCP_PROJECT": {"value": "b"}}, "p": {"GCP_PROJECT": {"value": "b"}}},
            "participants": ["Broad", "p"],
            "setup_configuration": "website",
        },
        "role",
    )

    google_cloud_compute.setup_networking(
        {
            "personal_parameters": {"Broad": {"GCP_PROJECT": {"value": "b"}}, "p": {"GCP_PROJECT": {"value": "b"}}},
            "participants": ["Broad", "p"],
            "setup_configuration": "user",
        },
        "role",
    )


def test_delete_everything(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.remove_conflicting_peerings", return_value=None)
    mocker.patch(f"{patch_prefix}.list_instances", return_value=["alpha-sfkit", "bad", "name1"])
    mocker.patch(f"{patch_prefix}.delete_instance", return_value=None)
    mocker.patch(f"{patch_prefix}.delete_firewall", return_value=None)
    mocker.patch(f"{patch_prefix}.delete_subnet", return_value=None)
    mocker.patch(f"{patch_prefix}.delete_network", return_value=None)

    google_cloud_compute = GoogleCloudCompute("alpha", "")
    google_cloud_compute.delete_everything()

    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.delete_everything()

    google_cloud_compute.firewall_name = "garbage"
    google_cloud_compute.delete_everything()


def test_create_network_if_it_does_not_already_exist(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.wait_for_operation", return_value=None)
    mocker.patch(f"{patch_prefix}.create_firewall", return_value=None)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.create_network_if_it_does_not_already_exist({})

    google_cloud_compute = GoogleCloudCompute("subnet0", "subnet")
    google_cloud_compute.create_network_if_it_does_not_already_exist({})


def test_delete_network(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    # sourcery skip: extract-duplicate-method
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.delete_network()

    google_cloud_compute = GoogleCloudCompute("subnet0", "subnet")
    google_cloud_compute.delete_network()

    google_cloud_compute = GoogleCloudCompute("subnet0", "")
    google_cloud_compute.delete_network()


def test_create_firewall(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.wait_for_operation", return_value=None)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.create_firewall({"participants": []})

    google_cloud_compute = GoogleCloudCompute("subnet0", "subnet")
    google_cloud_compute.create_firewall(
        {
            "participants": ["user1", "user2"],
            "personal_parameters": {"user1": {"IP_ADDRESS": {"value": 8000}}, "user2": {"IP_ADDRESS": {"value": ""}}},
        }
    )


def test_delete_firewall(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.delete_firewall("test")


def test_remove_conflicting_peerings(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    assert google_cloud_compute.remove_conflicting_peerings(["broad-cho-priv1"])

    google_cloud_compute = GoogleCloudCompute("", "")
    assert not google_cloud_compute.remove_conflicting_peerings(["broad-cho-priv1"])

    google_cloud_compute.remove_conflicting_peerings()


def test_remove_conflicting_subnets(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.delete_subnet", return_value=None)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.remove_conflicting_subnets(["broad-cho-priv1", "peeringproject2", "project3"])

    google_cloud_compute = GoogleCloudCompute("subnet0", "subnet")
    google_cloud_compute.remove_conflicting_subnets(["subnet", "peeringproject2", "project3"])

    # assert False


def test_delete_subnet(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.list_instances", return_value=["name"])
    mocker.patch(f"{patch_prefix}.delete_instance", return_value=None)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.delete_subnet({"name": "name", "selfLink": "link"})

    try:
        with pytest.raises(Exception) as _:
            google_cloud_compute.delete_subnet({"name": "sfkit-subnet0", "selfLink": "link"})
    except Exception as e:
        if "RetryError" not in str(e):
            raise e from e


def test_create_subnet(
    mocker: Callable[..., Generator[MockerFixture, None, None]]
):  # sourcery skip: extract-duplicate-method
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.create_subnet("0")
    google_cloud_compute.create_subnet("role")

    google_cloud_compute = GoogleCloudCompute("subnet0", "subnet")
    google_cloud_compute.create_subnet("0")
    google_cloud_compute.create_subnet("role")


def test_create_peerings(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.create_peerings(gcp_projects=["broad-cho-priv1", "peeringproject2", "project3"])


def test_setup_instance(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.list_instances", return_value=["name"])
    mocker.patch(f"{patch_prefix}.delete_instance", return_value=None)
    mocker.patch(f"{patch_prefix}.create_instance", return_value=None)
    mocker.patch(f"{patch_prefix}.get_vm_external_ip_address", return_value=None)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")

    google_cloud_compute.setup_instance("name", "role", ["metadata"])

    mocker.patch(f"{patch_prefix}.list_instances", return_value=[])
    google_cloud_compute.setup_instance("name", "role", ["metadata"])

    mocker.patch(f"{patch_prefix}.create_instance", side_effect=Exception("test"))
    with pytest.raises(Exception) as _:
        google_cloud_compute.setup_instance("name", "role", ["metadata"])

    mocker.patch(f"{patch_prefix}.create_instance", side_effect=Exception("zonesAvailable': 'us-east1-b, us-east1-c"))
    with pytest.raises(Exception) as _:
        google_cloud_compute.setup_instance("name", "role", ["metadata"])


def test_create_instance(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.wait_for_zone_operation", return_value=None)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.create_instance("name", "role", 16, 16, [])
    google_cloud_compute.create_instance("name", "role", 16, 16, ["metadata"])
    google_cloud_compute.create_instance("name", "role", 64, 64, ["metadata"])


def test_stop_instance(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.stop_instance("name")


def test_list_instances(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.list_instances()

    google_cloud_compute = GoogleCloudCompute("", "")
    google_cloud_compute.list_instances("subnetwork")


def test_delete_instance(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.delete_instance(name="name")


def test_wait_for_operation(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.wait_for_operation(operation="operation")

    MockExecutable.error = "fake error"

    with pytest.raises(Exception) as _:
        google_cloud_compute.wait_for_operation(operation="operation")


def test_wait_for_zoneOperation(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.wait_for_zone_operation(zone="zone", operation="operation")

    MockExecutable.error = "fake error"

    with pytest.raises(Exception) as _:
        google_cloud_compute.wait_for_zone_operation(zone="zone", operation="operation")


def test_wait_for_regionOperation(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.wait_for_region_operation(region="region", operation="operation")

    MockExecutable.error = "fake error"

    with pytest.raises(Exception) as _:
        google_cloud_compute.wait_for_region_operation("region", "operation")


def test_return_result_or_error(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    google_cloud_compute.return_result_or_error({"error": "RESOURCE_NOT_FOUND"})


def test_vm_external_ip_address(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("alpha", "broad-cho-priv1")
    assert google_cloud_compute.get_vm_external_ip_address("name") == "1877.0.0.1"


def test_create_instance_name():
    assert create_instance_name("testtitle", "1") == "testtitle-sfkit1"


def setup_mocking(mocker):
    mocker.patch("src.utils.google_cloud.google_cloud_compute.create_instance_name", return_value="name")
    mocker.patch("src.utils.google_cloud.google_cloud_compute.logger.error", return_value=None)
    mocker.patch("src.utils.google_cloud.google_cloud_compute.sleep", lambda x: None)
    mocker.patch("time.sleep", lambda x: None)
    mocker.patch("src.utils.google_cloud.google_cloud_compute.googleapi.build", return_value=MockCompute())
    MockOperations.trial = 0
    MockExecutable.error = ""
    MockExecutable.status = "RUNNING"


class MockCompute:
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
    trial: int

    def get(self, project, operation, region=None, zone=None):
        MockOperations.trial += 1
        if MockOperations.trial > 1:
            MockExecutable.status = "DONE"
        return MockExecutable()


class MockInsertable:
    def list(self, project=None, region=None, zone=None, firewall=None):
        # sourcery skip: raise-specific-error
        if project == "":
            raise Exception("no instances")
        if region == "":
            raise Exception("list failed")
        return MockExecutable()

    def insert(self, project=None, zone=None, region=None, body=None):
        return MockExecutable()

    def get(self, project=None, network=None, zone=None, instance=None):
        # sourcery skip: raise-specific-error
        if project == "":
            raise Exception("get failed")
        return MockExecutable()

    def delete(
        self, project=None, zone=None, region=None, subnetwork=None, instance=None, firewall=None, network=None
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
    status: str = "RUNNING"
    networkName1: str = f"{constants.NETWORK_NAME_ROOT}-alpha"
    networkName2: str = f"{constants.NETWORK_NAME_ROOT}-alpha"
    project: str = "broad-cho-priv1"
    error: str = ""
    creationTimestamp: str = "2020-04-01T00:00:00Z"

    def execute(self):
        res = {
            "items": [
                {
                    "name": MockExecutable.networkName1,
                    "creationTimestamp": MockExecutable.creationTimestamp,
                    "selfLink": "hi",
                    "network": "broad-cho-priv1",
                    "ipCidrRange": "10.0.0.0/24",
                    "networkInterfaces": [{"subnetwork": "hi"}],
                },
                {
                    "name": "sfkit-alpha-subnet0",
                    "creationTimestamp": MockExecutable.creationTimestamp,
                    "selfLink": "hi",
                    "network": "sfkit-alpha-subnet0",
                    "ipCidrRange": "0.0.0.0/0",
                    "networkInterfaces": [{"subnetwork": "hi"}],
                },
                {
                    "name": "sfkit-subnet0",
                    "creationTimestamp": MockExecutable.creationTimestamp,
                    "selfLink": "hi",
                    "network": "sfkit-subnet0",
                    "ipCidrRange": "10.0.2.0/24",
                    "networkInterfaces": [{"subnetwork": "hi"}],
                },
                {
                    "name": "garbage",
                    "creationTimestamp": MockExecutable.creationTimestamp,
                    "selfLink": "hi",
                    "network": "sfkit",
                    "ipCidrRange": "10.0.2.0/24",
                    "networkInterfaces": [{"subnetwork": "hi"}],
                },
            ],
            "status": MockExecutable.status,
            "name": "operation",
            "network": "broad-cho-priv1",
            "selfLink": "selfLink",
            "networkInterfaces": [{"accessConfigs": [{"natIP": "1877.0.0.1"}]}],
            "peerings": [
                {"name": f"peering-{MockExecutable.project}"},
                {"name": "peering-peeringproject2"},
            ],
            "serviceAccounts": [{"email": "test_email@email.com"}],
        }
        if MockExecutable.error:
            res["error"] = "fake error"
        MockExecutable.networkName1 = constants.NETWORK_NAME_ROOT
        return res
