# deprecated

# import socket

# from google.cloud.pubsub_v1.publisher.client import publisher_client
# from google.cloud.pubsub_v1.subscriber.client import subscriber_client


# class GoogleCloudPubsub:
#     """
#     Class to handle interactions with Google Cloud Pub/Sub
#     """

#     def __init__(self, project: str, role: str, study_title: str) -> None:
#         self.project = project
#         self.publisher = publisher_client.PublisherClient()
#         self.subscriber = subscriber_client.SubscriberClient()

#         self.topic_id = study_title.replace(" ", "").lower() + "-" + "secure-gwas" + role
#         self.subscription_id = f"{socket.gethostname()}-subscribing-to-{self.topic_id}"
#         self.project_path = f"projects/{self.project}"
#         self.topic_path = self.publisher.topic_path(self.project, self.topic_id)
#         self.subscription_path = self.subscriber.subscription_path(self.project, self.subscription_id)

#     def create_topic_and_subscribe(self, topic_name: str = "") -> None:
#         if topic_name:
#             self.topic_path = self.publisher.topic_path(self.project, topic_name)

#         topic_list = self.publisher.list_topics(request={"project": self.project_path})
#         topic_list = [str(topic).split('"')[1] for topic in topic_list]
#         if self.topic_path not in topic_list:
#             print(f"Creating topic {self.topic_path}")
#             self.publisher.create_topic(name=self.topic_path)

#         subscription_list = self.subscriber.list_subscriptions(request={"project": self.project_path})
#         subscription_list = [str(topic).split('"')[1] for topic in subscription_list]

#         if self.subscription_path in subscription_list:
#             print(f"Subscription {self.subscription_path} already exists")
#         else:
#             print(f"Creating subscription {self.subscription_path}")
#             self.subscriber.create_subscription(
#                 request={
#                     "name": self.subscription_path,
#                     "topic": self.topic_path,
#                     # "enable_exactly_once_delivery": True, # cannot do this with message ordering
#                     "enable_message_ordering": True,
#                     "push_config": {
#                         "push_endpoint": "https://secure-gwas-website-bhj5a4wkqa-uc.a.run.app/",
#                     },
#                 }
#             )

#     def delete_topics_and_subscriptions(self) -> None:
#         try:
#             print(f"Deleting topic {self.topic_path}")
#             self.publisher.delete_topic(request={"topic": self.topic_path})
#             print(f"Deleting subscription {self.subscription_path}")
#             self.subscriber.delete_subscription(request={"subscription": self.subscription_path})
#         except publisher_client.core_exceptions.NotFound:  # type: ignore
#             print(f"Topic or subscription {self.topic_id} does not exist to delete")

#     def add_pub_iam_member(self, role: str, member: str) -> None:
#         policy = self.publisher.get_iam_policy(request={"resource": self.topic_path})  # type: ignore
#         policy.bindings.add(role=role, members=[member])  # type: ignore
#         policy = self.publisher.set_iam_policy(request={"resource": self.topic_path, "policy": policy})  # type: ignore

#         print(f"IAM policy for topic: {self.topic_id} updated to give role: {role} to member: {member}")
