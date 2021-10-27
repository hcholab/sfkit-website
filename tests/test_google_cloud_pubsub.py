import pytest
from src.utils.google_cloud.google_cloud_pubsub import GoogleCloudPubsub


def setup_mocking(mocker):
    mocker.patch(
        "src.utils.google_cloud.google_cloud_pubsub.pubsub_v1.PublisherClient",
        MockPublisherClient,
    )
    mocker.patch(
        "src.utils.google_cloud.google_cloud_pubsub.pubsub_v1.SubscriberClient",
        MockSubscriberClient,
    )


@pytest.mark.parametrize(("project"), (("broad-cho-priv1"), ("bad")))
def test_create_topic_and_subscribe(mocker, project):
    setup_mocking(mocker)
    google_cloud_pubsub = GoogleCloudPubsub(project, "0", "project title")
    google_cloud_pubsub.create_topic_and_subscribe()


def test_listen_to_startup_script(mocker):
    setup_mocking(mocker)
    google_cloud_pubsub = GoogleCloudPubsub("broad-cho-priv1", "0", "project title")
    google_cloud_pubsub.listen_to_startup_script("status")


def test_listen_to_startup_script_with_error(mocker):
    setup_mocking(mocker)
    google_cloud_pubsub = GoogleCloudPubsub("bad", "0", "project title")

    with pytest.raises(Exception):
        google_cloud_pubsub.listen_to_startup_script("status")


def test_add_pub_iam_member(mocker):
    setup_mocking(mocker)
    google_cloud_pubsub = GoogleCloudPubsub("broad-cho-priv1", "0", "project title")
    google_cloud_pubsub.add_pub_iam_member("role", "member")


class MockPublisherClient:
    def topic_path(self, project, topic):
        return project

    def list_topics(self, request):
        return ['blah"broad-cho-priv1']

    def create_topic(self, name):
        pass

    def get_iam_policy(self, request):
        return MockPolicy()

    def set_iam_policy(self, request):
        return MockPolicy()


class MockSubscriberClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def subscription_path(self, project, subscription):
        return project

    def list_subscriptions(self, request):
        return ['blah"broad-cho-priv1']

    def create_subscription(self, request):
        pass

    def delete_subscription(self, request):
        pass

    def subscribe(self, path, callback):
        return MockStreamingPullFuture(path, callback)


class MockStreamingPullFuture:
    def __init__(self, path, callback):
        self.path = path
        self.callback = callback

    def result(self, timeout=None):
        if self.path == "bad":
            raise Exception("bad")
        if timeout is not None:
            raise TimeoutError()
        self.callback(MockMessage())

    def cancel(self):
        pass


class MockPolicy:
    def __init__(self):
        self.bindings = MockBinding()


class MockBinding:
    def add(self, role, members):
        pass


class MockMessage:
    def __init__(self):
        self.data = b"data"

    def ack(self):
        pass
