import pytest
from src.utils import constants
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute


def setup_mocking(mocker):
    mocker.patch("time.sleep", lambda x: None)
    mocker.patch(
        "src.utils.google_cloud.google_cloud_compute.googleapi",
        MockMakeMockCompute,
    )
    MockExecutable.error = ""


@pytest.mark.parametrize(
    ("networkName1", "networkName2", "status", "creationTimestamp", "project", "error"),
    (
        (
            constants.NETWORK_NAME,
            constants.NETWORK_NAME,
            "RUNNING",
            "newTimestamp",
            "broad-cho-priv1",
            None,
        ),
        (
            constants.NETWORK_NAME,
            constants.NETWORK_NAME,
            "RUNNING",
            "2020-04-01T00:00:00Z",
            "broad-cho-priv1",
            None,
        ),
        (
            constants.NETWORK_NAME,
            constants.NETWORK_NAME,
            "RUNNING",
            "newTimestamp",
            "broad-cho-priv1",
            "fake error",
        ),
        ("1", "1", "RUNNING", "2020-04-01T00:00:00Z", "broad-cho-priv2", None),
        ("1", "1", "RUNNING", "2020-04-01T00:00:00Z", "broad-cho-priv2", "fake error"),
    ),
)
def test_setup_networking(
    mocker, networkName1, networkName2, status, creationTimestamp, project, error
):
    setup_mocking(mocker)
    MockExecutable.networkName1 = networkName1
    MockExecutable.networkName2 = networkName2
    MockExecutable.status = status
    MockExecutable.creationTimestamp = creationTimestamp
    MockExecutable.project = project
    MockExecutable.error = error

    MockOperations.trial = 0
    google_cloud_compute = GoogleCloudCompute(project)

    doc_ref_dict = {
        "participants": ["a", "b"],
        "personal_parameters": {
            "a": {
                "GCP_PROJECT": {
                    "value": "broad-cho-priv1",
                }
            },
            "b": {
                "GCP_PROJECT": {
                    "value": "broad-cho-priv1",
                }
            },
        },
    }
    try:
        google_cloud_compute.setup_networking(doc_ref_dict, "0")
    except Exception as e:
        if str(e) != "fake error" and "RetryError" not in str(e):
            raise


@pytest.mark.parametrize(
    ("networkName1", "networkName2", "status", "creationTimestamp", "project", "error"),
    (
        (
            constants.NETWORK_NAME,
            constants.NETWORK_NAME,
            "RUNNING",
            "newTimestamp",
            "broad-cho-priv1",
            None,
        ),
        ("1", "1", "RUNNING", "2020-04-01T00:00:00Z", "broad-cho-priv2", None),
        ("1", "1", "RUNNING", "2020-04-01T00:00:00Z", "broad-cho-priv2", "fake error"),
    ),
)
def test_setup_instance(
    mocker, networkName1, networkName2, status, creationTimestamp, project, error
):
    setup_mocking(mocker)
    MockExecutable.networkName1 = networkName1
    MockExecutable.networkName2 = networkName2
    MockExecutable.status = status
    MockExecutable.creationTimestamp = creationTimestamp
    MockExecutable.project = project
    MockExecutable.error = error

    MockOperations.trial = 0
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")

    try:
        google_cloud_compute.setup_instance(
            zone="zone", name=constants.NETWORK_NAME, role="role", num_cpus=4
        )
    except Exception as e:
        if str(e) != "fake error" and "RetryError" not in str(e):
            raise


def test_create_instance(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.create_instance(
        zone="zone",
        name=constants.NETWORK_NAME,
        role="role",
        num_cpus=4,
        validate=True,
        metadata="hi",
    )


def test_stop_instance(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")

    try:
        google_cloud_compute.stop_instance(zone="zone", instance="name")
    except Exception as e:
        if str(e) != "fake error" and "RetryError" not in str(e):
            raise


def test_get_service_account_for_vm(mocker):
    setup_mocking(mocker)
    google_cloud_compute = GoogleCloudCompute("broad-cho-priv1")
    google_cloud_compute.get_service_account_for_vm(zone="zone", instance="name")


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
    status: str
    networkName1: str
    networkName2: str
    project: str
    error: str
    creationTimestamp: str

    def execute(self):
        res = {
            "items": [
                {
                    "name": MockExecutable.networkName1,
                    "creationTimestamp": MockExecutable.creationTimestamp,
                    "selfLink": "hi",
                    "network": "broad-cho-priv1",
                    "networkInterfaces": [{"subnetwork": "hi"}],
                },
                {
                    "name": MockExecutable.networkName2,
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
            "networkInterfaces": [{"accessConfigs": [{"natIP": "hi"}]}],
            "peerings": [{"name": f"peering-{MockExecutable.project}"}],
            "serviceAccounts": [{"email": "hi"}],
        }
        if MockExecutable.error:
            res["error"] = "fake error"
        MockExecutable.networkName1 = constants.NETWORK_NAME
        return res
