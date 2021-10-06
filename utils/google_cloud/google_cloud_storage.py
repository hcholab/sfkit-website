
from sys import prefix
import time

import constants
from google.cloud import storage
from utils.google_cloud_general import GoogleCloudGeneral


class GoogleCloudStorage(GoogleCloudGeneral):

    def __init__(self, project) -> None:
        super().__init__(project)
        self.storage_client = storage.Client(project=self.project)

    def validate_bucket(self, role):
        buckets_list = [bucket.name for bucket in self.storage_client.list_buckets()]

        if constants.BUCKET_NAME not in buckets_list:
            print(f"Creating bucket {constants.BUCKET_NAME}")
            self.storage_client.create_bucket(constants.BUCKET_NAME)
            time.sleep(1)

        self.delete_blob(constants.BUCKET_NAME, "ip_addresses/IP_ADDR_P" + role)

        return self.storage_client.bucket(constants.BUCKET_NAME)
    
    def add_bucket_iam_member(self, bucket_name, role, member):
        """Add a new member to an IAM Policy"""
        # bucket_name = "your-bucket-name"
        # role = "IAM role, e.g., roles/storage.objectViewer"
        # member = "IAM identity, e.g., user: name@example.com"

        bucket = self.storage_client.bucket(bucket_name)

        policy = bucket.get_iam_policy(requested_policy_version=3)

        policy.bindings.append({"role": role, "members": {member}})

        bucket.set_iam_policy(policy)

        print("Added {} with role {} to {}.".format(member, role, bucket_name))

    def get_ip_addresses_from_bucket(self):
        print("Getting ip_addresses from bucket")
        for i in range(1001):
            if len(list(self.storage_client.list_blobs(constants.BUCKET_NAME, prefix="ip_addresses/"))) < 4:
                time.sleep(1)
            else:
                break
            if i == 1000:
                print("The other parties don't seem to be showing up...")
                raise Exception(
                    "The other parties don't seem to be showing up...")
        ip_addresses = []
        for role in ["0", "1", "2", "3"]:
            bucket = self.storage_client.bucket(constants.BUCKET_NAME)
            blob = bucket.blob("ip_addresses/IP_ADDR_P" + role)
            ip_address = blob.download_as_bytes()
            ip_addresses.append(
                ("IP_ADDR_P" + role, ip_address.decode("utf-8")))
        return ip_addresses

    def delete_blob(self, bucket_name, blob_name):
        """Deletes a blob from the bucket."""
        # bucket_name = "your-bucket-name"
        # blob_name = "your-object-name"
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        if blob.name in [b.name for b in bucket.list_blobs()]:
            blob.delete()
            print("Blob {} deleted.".format(blob_name))
        else:
            print(f"Blob {blob_name} didn't exist")
