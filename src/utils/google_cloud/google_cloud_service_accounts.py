import base64

import googleapiclient.discovery
from src.utils import constants
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM


def setup_service_account_and_key(study_title: str, user_email: str) -> list:
    service_accounts = list_service_accounts("broad-cho-priv1")

    name = "".join(c for c in user_email if c not in "@.")
    display_name = f"Service Account for user {user_email} in study {study_title}"

    # if the service account doesn't already exist, create it
    sa_email = f"{name}@{constants.SERVER_GCP_PROJECT}.iam.gserviceaccount.com"
    if all(sa["email"] != sa_email for sa in service_accounts):
        create_service_account(constants.SERVER_GCP_PROJECT, name, display_name)

    gcloudIAM = GoogleCloudIAM()
    gcloudIAM.give_minimal_required_gcp_permissions(sa_email, member_type="serviceAccount")

    return [sa_email, create_key(sa_email)]


def create_service_account(project_id: str, name: str, display_name: str) -> dict:
    """Creates a service account."""

    service = googleapiclient.discovery.build("iam", "v1")
    my_service_account = (
        service.projects()
        .serviceAccounts()
        .create(
            name=f"projects/{project_id}", body={"accountId": name, "serviceAccount": {"displayName": display_name}}
        )
        .execute()
    )
    print("Created service account: " + my_service_account["email"])
    return my_service_account


def list_service_accounts(project_id: str) -> list:
    """Lists service accounts in a project."""

    service = googleapiclient.discovery.build("iam", "v1")
    response = service.projects().serviceAccounts().list(name=f"projects/{project_id}").execute()
    for account in response["accounts"]:
        print(account["name"])
    return response["accounts"]


def create_key(service_account_email: str) -> str:
    """Creates a key for a service account."""

    service = googleapiclient.discovery.build("iam", "v1")
    key = (
        service.projects()
        .serviceAccounts()
        .keys()
        .create(name=f"projects/-/serviceAccounts/{service_account_email}", body={})
        .execute()
    )
    return base64.b64decode(key["privateKeyData"]).decode("utf-8")


def delete_service_account(project_id: str, sa_email: str) -> None:
    """Deletes a service account."""

    service = googleapiclient.discovery.build("iam", "v1")
    service.projects().serviceAccounts().delete(name=f"projects/{project_id}/serviceAccounts/{sa_email}").execute()
    print(f"Deleted service account: {sa_email}")
