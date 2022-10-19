import fileinput
import os

from flask import current_app
from google.cloud import storage
from src.utils import constants


class GoogleCloudStorage:
    """
    Class to handle interactions with Google Cloud Storage
    """

    def __init__(self, project) -> None:
        self.project = project
        self.storage_client = storage.Client(project=self.project)

    def add_bucket_iam_member(self, bucket_name: str, role: str, member: str) -> None:
        """Add a new member to an IAM Policy"""
        # bucket_name = "your-bucket-name"
        # role = "IAM role, e.g., roles/storage.objectViewer"
        # member = "IAM identity, e.g., user: name@example.com"

        bucket = self.storage_client.bucket(bucket_name)
        policy = bucket.get_iam_policy(requested_policy_version=3)
        policy.bindings.append({"role": role, "members": {member}})
        bucket.set_iam_policy(policy)
        print(f"Added {member} with role {role} to {bucket_name}.")

    def copy_parameters_to_bucket(
        self,
        study_title: str,
        bucket_name: str = constants.PARAMETER_BUCKET,
    ) -> None:
        print(f"Copying parameters to bucket {bucket_name}")
        bucket = self.storage_client.bucket(bucket_name)
        for filename in constants.PARAMETER_FILES:
            blob = bucket.blob(filename)
            blob.download_to_filename(os.path.join(constants.TEMP_FOLDER, filename))
            self.update_parameters(os.path.join(constants.TEMP_FOLDER, filename), study_title)
            blob.upload_from_filename(os.path.join(constants.TEMP_FOLDER, filename))
        print(f"Updated parameters in {constants.PARAMETER_FILES}")

    def update_parameters(self, file: str, study_title: str) -> None:
        print(f"Updating parameters in {file}")

        doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title.replace(" ", "").lower())
        doc_ref_dict: dict = doc_ref.get().to_dict()

        pars = doc_ref_dict["parameters"]

        file_number = file.split(".")[-2]
        pars = pars | doc_ref_dict["personal_parameters"][doc_ref_dict["participants"][int(file_number)]]

        pars["NUM_INDS_SP_1"] = doc_ref_dict["personal_parameters"][doc_ref_dict["participants"][1]]["NUM_INDS"]
        pars["NUM_INDS_SP_2"] = doc_ref_dict["personal_parameters"][doc_ref_dict["participants"][2]]["NUM_INDS"]
        pars["NUM_INDS"] = {"value": ""}
        pars["NUM_INDS"]["value"] = str(int(pars["NUM_INDS_SP_1"]["value"]) + int(pars["NUM_INDS_SP_2"]["value"]))

        # update pars with ipaddresses
        for i in range(3):
            pars[f"IP_ADDR_P{str(i)}"] = doc_ref_dict["personal_parameters"][doc_ref_dict["participants"][i]][
                "IP_ADDRESS"
            ]
        # update pars with ports
        # pars["PORT_P0_P1"] and PORT_P0_P2 do not need to be updated as they are controlled by us (the Broad)
        pars["PORT_P1_P2"] = {
            "value": doc_ref_dict["personal_parameters"][doc_ref_dict["participants"][1]]["PORTS"]["value"].split(",")[
                2
            ]
        }

        for line in fileinput.input(file, inplace=True):
            key = str(line).split(" ")[0]
            if key in pars:
                line = f"{key} " + str(pars[key]["value"]) + "\n"
            print(line, end="")

    def upload_to_bucket(self, file: str, filename: str, bucket_name: str = constants.PARAMETER_BUCKET) -> None:
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_file(file)
        print(f"Uploaded {filename} to bucket")

    def check_file_exists(self, filename: str, bucket_name: str = constants.PARAMETER_BUCKET) -> bool:
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        return blob.name in [b.name for b in bucket.list_blobs()]
