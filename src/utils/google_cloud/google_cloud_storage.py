import fileinput
import os

from flask import current_app
from google.cloud import storage
from src.utils import constants


class GoogleCloudStorage:
    def __init__(self, project) -> None:
        self.project = project
        self.storage_client = storage.Client(project=self.project)

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

    def copy_parameters_to_bucket(self, study_title, role):
        bucket = self.storage_client.bucket(constants.BUCKET_NAME)
        for filename in constants.PARAMETER_FILES:
            blob = bucket.blob(filename)
            blob.download_to_filename(os.path.join(constants.TEMP_FOLDER, filename))
            self.update_parameters(
                os.path.join(constants.TEMP_FOLDER, filename), study_title, role
            )
            blob.upload_from_filename(os.path.join(constants.TEMP_FOLDER, filename))
            print(f"Updated parameters in {filename}")

    def update_parameters(self, file, study_title, role):
        db = current_app.config["DATABASE"]
        doc_dict = (
            db.collection("studies")
            .document(study_title.replace(" ", "").lower())
            .get()
            .to_dict()
        )
        parameters = doc_dict["parameters"]

        if role == file.split(".")[-2]:
            parameters = (
                parameters
                | doc_dict["personal_parameters"][
                    doc_dict["participants"][int(role) - 1]
                ]
            )

        for line in fileinput.input(file, inplace=True):
            key = str(line).split(" ")[0]
            if key in parameters:
                line = f"{key} " + str(parameters[key]["value"]) + "\n"
            print(line, end="")

    def upload_to_bucket(self, file, filename):
        bucket = self.storage_client.bucket(constants.BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_file(file)
        print(f"Uploaded {filename} to bucket")

    def check_file_exists(self, filename):
        bucket = self.storage_client.bucket(constants.BUCKET_NAME)
        blob = bucket.blob(filename)
        return blob.name in [b.name for b in bucket.list_blobs()]
