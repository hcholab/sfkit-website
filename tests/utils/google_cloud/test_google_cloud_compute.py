# sourcery skip: do-not-use-staticmethod, snake-case-functions
import pytest
from src.utils import constants
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute

patch_prefix = "src.utils.google_cloud.google_cloud_compute.GoogleCloudCompute"


def test_setup_networking(mocker):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.create_network", return_value=None)
    mocker.patch(f"{patch_prefix}.remove_conflicting_peerings", return_value=None)
    mocker.patch(f"{patch_prefix}.remove_conflicting_subnets", return_value=None)
    mocker.patch(f"{patch_prefix}.create_subnet", return_value=None)
    mocker.patch(f"{patch_prefix}.create_peerings", return_value=None)

    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.setup_networking(
        {
            "personal_parameters": {"Broad": {"GCP_PROJECT": {"value": "b"}}, "p": {"GCP_PROJECT": {"value": "b"}}},
            "participants": ["Broad", "p"],
        },
        "role",
    )


def test_create_network(mocker):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.wait_for_operation", return_value=None)
    mocker.patch(f"{patch_prefix}.create_firewall", return_value=None)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.create_network()
    google_cloud_compute.create_network("bad_name")


def test_create_firewall(mocker):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.wait_for_operation", return_value=None)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.create_firewall()

    google_cloud_compute = GoogleCloudCompute("blah-blah-blah")
    google_cloud_compute.create_firewall()


def test_remove_conflicting_peerings(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.remove_conflicting_peerings(["broad-cho-priv1"])


def test_remove_conflicting_subnets(mocker):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.delete_subnet", return_value=None)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.remove_conflicting_subnets(["broad-cho-priv1", "peeringproject2", "project3"])


def test_delete_subnet(mocker):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.list_instances", return_value=["name"])
    mocker.patch(f"{patch_prefix}.delete_instance", return_value=None)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.delete_subnet({"name": "name", "selfLink": "link"})

    try:
        with pytest.raises(Exception) as _:
            google_cloud_compute.delete_subnet({"name": "secure-gwas-subnet0", "selfLink": "link"})
    except Exception as e:
        if "RetryError" not in str(e):
            raise e from e


def test_create_subnet(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.create_subnet("0")
    google_cloud_compute.create_subnet("role")


def test_create_peerings(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.create_peerings(gcp_projects=["broad-cho-priv1", "peeringproject2", "project3"])


# def test_setup_instance(mocker):
#     setup_mocking(mocker)
#     mocker.patch(f"{patch_prefix}.list_instances", return_value=[])
#     mocker.patch(f"{patch_prefix}.delete_instance", return_value=None)
#     mocker.patch(f"{patch_prefix}.create_instance", return_value=None)
#     mocker.patch(f"{patch_prefix}.get_vm_external_ip_address", return_value=None)
#     google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")

#     google_cloud_compute.setup_instance("zone", "name", "role", {})

#     mocker.patch(f"{patch_prefix}.list_instances", return_value=["name"])
#     google_cloud_compute.setup_instance("zone", "name", "role", {})


# def test_create_instance(mocker):
#     setup_mocking(mocker)
#     mocker.patch(f"{patch_prefix}.wait_for_zone_operation", return_value=None)
#     google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
#     google_cloud_compute.create_instance("zone", constants.NETWORK_NAME, "role", 10, 4, {}, startup_script="validate")
#     google_cloud_compute.create_instance("zone", constants.NETWORK_NAME, "role", 10, 4, {})


def test_stop_instance(mocker):
    setup_mocking(mocker)
    mocker.patch(f"{patch_prefix}.wait_for_zone_operation", return_value=None)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.stop_instance(zone=constants.SERVER_ZONE, instance="name")


def test_list_instances(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.list_instances()


def test_delete_instance(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.delete_instance(name="name")


def test_wait_for_operation(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.wait_for_operation(operation="operation")

    MockExecutable.error = "fake error"

    with pytest.raises(Exception) as _:
        google_cloud_compute.wait_for_operation(operation="operation")


def test_wait_for_zoneOperation(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.wait_for_zone_operation(zone="zone", operation="operation")

    MockExecutable.error = "fake error"

    with pytest.raises(Exception) as _:
        google_cloud_compute.wait_for_zone_operation(zone="zone", operation="operation")


def test_wait_for_regionOperation(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.wait_for_region_operation(region="region", operation="operation")

    MockExecutable.error = "fake error"

    with pytest.raises(Exception) as _:
        google_cloud_compute.wait_for_region_operation("region", "operation")


def test_vm_external_ip_address(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    assert google_cloud_compute.get_vm_external_ip_address("zone", "name") == "1877.0.0.1"


def test_get_service_account_for_vm(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    assert google_cloud_compute.get_service_account_for_vm("zone", "name") == "test_email@email.com"


def setup_mocking(mocker):
    mocker.patch("src.utils.google_cloud.google_cloud_compute.sleep", lambda x: None)
    mocker.patch("time.sleep", lambda x: None)
    mocker.patch(
        "src.utils.google_cloud.google_cloud_compute.googleapi",
        MockMakeMockCompute,
    )
    MockOperations.trial = 0
    MockExecutable.error = ""
    MockExecutable.status = "RUNNING"


class MockMakeMockCompute:
    @staticmethod
    def build(api, version):
        return MockCompute()


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
    def list(self, project=None, region=None, zone=None):
        return MockExecutable()

    def insert(self, project=None, zone=None, region=None, body=None):
        return MockExecutable()

    def get(self, project=None, network=None, zone=None, instance=None):
        return MockExecutable()

    def delete(self, project=None, zone=None, region=None, subnetwork=None, instance=None):
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
    networkName1: str = constants.NETWORK_NAME
    networkName2: str = constants.NETWORK_NAME
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
                    "name": "secure-gwas-subnet0",
                    "creationTimestamp": MockExecutable.creationTimestamp,
                    "selfLink": "hi",
                    "network": "secure-gwas",
                    "ipCidrRange": "0.0.0.0/0",
                    "networkInterfaces": [{"subnetwork": "hi"}],
                },
                {
                    "name": "secure-gwas-subnet0",
                    "creationTimestamp": MockExecutable.creationTimestamp,
                    "selfLink": "hi",
                    "network": "secure-gwas",
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
        MockExecutable.networkName1 = constants.NETWORK_NAME
        return res
