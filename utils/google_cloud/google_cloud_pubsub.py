import socket
from concurrent.futures import TimeoutError

from google.cloud import pubsub_v1


class GoogleCloudPubsub():
    def __init__(self, project, role) -> None:
        self.project = project
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()

        self.topic_id = "secure-gwas" + role
        self.subscription_id = socket.gethostname() + "-subscribing-to-" + self.topic_id
        self.project_path = f"projects/{self.project}"
        self.topic_path = self.publisher.topic_path(
            self.project, self.topic_id)
        self.subscription_path = self.subscriber.subscription_path(
            self.project, self.subscription_id)

    def create_topic_and_subscribe(self) -> None:
        topic_list = self.publisher.list_topics(
            request={"project": self.project_path})
        topic_list = list(
            map(lambda topic: str(topic).split('"')[1], topic_list))
        if self.topic_path not in topic_list:
            print(f"Creating topic {self.topic_path}")
            self.publisher.create_topic(name=self.topic_path)

        subscription_list = self.subscriber.list_subscriptions(
            request={"project": self.project_path})
        subscription_list = list(
            map(lambda topic: str(topic).split('"')[1], subscription_list))
        if self.subscription_path in subscription_list:
            print(f"Deleting subscription {self.subscription_path}")
            self.subscriber.delete_subscription(
                request={"subscription": self.subscription_path})
        print(f"Creating subscription {self.subscription_path}")
        self.subscriber.create_subscription(
            name=self.subscription_path, topic=self.topic_path)

    def listen_to_startup_script(self, status):
        def callback(message: pubsub_v1.subscriber.message.Message) -> None:
            print(f"Received {message}.")
            message.ack()
            nonlocal status
            status = max(status, str(message.data.decode("utf-8")),
                         key=lambda x: x.split()[-1])

        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path, callback=callback)
        print(f"Listening for messages on topic {self.topic_path}...\n")

        with self.subscriber:
            try:
                streaming_pull_future.result(timeout=5)  # seconds
            except TimeoutError:
                streaming_pull_future.cancel()
                streaming_pull_future.result()

        return status

    def add_pub_iam_member(self, role: str, member: str) -> None:
        policy = self.publisher.get_iam_policy(
            request={"resource": self.topic_path})
        policy.bindings.add(role=role, members=[member])
        policy = self.publisher.set_iam_policy(
            request={"resource": self.topic_path, "policy": policy})

        print("IAM policy for topic {} set: {}".format(self.topic_id, policy))
