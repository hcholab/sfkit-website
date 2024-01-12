import asyncio
import os
import secrets
import time
from html import escape
from http import HTTPStatus
from typing import Any, Dict, Optional

import httpx
from google.cloud.firestore_v1 import DocumentReference
from jinja2 import Template
from python_http_client.exceptions import HTTPError
from quart import current_app, g
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail
from werkzeug.exceptions import HTTPException

from src.auth import get_service_account_headers
from src.utils import constants, custom_logging
from src.utils.google_cloud.google_cloud_compute import (GoogleCloudCompute,
                                                         format_instance_name)
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM

logger = custom_logging.setup_logging(__name__)

email_template = Template(
    """
<p>Hello!<br>{{ inviter }} has invited you to join the {{ study_title }} study on the sfkit website.  Click <a href='https://sfkit.org/accept_invitation/{{ study_title }}'>here</a> to accept the invitation. (Note: you will need to log in using this email address to accept the invitation.){% if invitation_message %}<br><br>Here is a message from {{ inviter }}:<br>{{ invitation_message }}{% endif %}</p>
"""
)


async def email(
    inviter: str, recipient: str, invitation_message: str, study_title: str
) -> int:
    """
    Sends an invitation email to the recipient.

    :param inviter: The name of the person inviting the recipient.
    :param recipient: The email address of the recipient.
    :param invitation_message: A custom message from the inviter.
    :param study_title: The title of the study the recipient is being invited to.
    :return: The status code of the email sending operation.
    """
    doc_ref_dict: dict = (
        await current_app.config["DATABASE"]
        .collection("meta")
        .document("sendgrid")
        .get()
    ).to_dict()
    sg = SendGridAPIClient(api_key=doc_ref_dict.get("api_key", ""))

    html_content = email_template.render(
        inviter=escape(inviter),
        invitation_message=escape(invitation_message),
        study_title=escape(study_title),
    )

    message = Mail(
        to_emails=recipient,
        from_email=Email(
            doc_ref_dict.get("from_email", ""), doc_ref_dict.get("from_user", "")
        ),
        subject=f"sfkit: Invitation to join {study_title} study",
        html_content=html_content,
    )
    message.add_bcc(doc_ref_dict.get("from_email", ""))

    try:
        response = sg.send(message)
        logger.info("Email sent")
        return response.status_code  # type: ignore

    except HTTPError as e:
        logger.error(f"Email failed to send: {e}")
        return e.status_code  # type: ignore


async def make_auth_key(study_id: str, user_id: str) -> str:
    """
    Generates an auth_key for the user and stores it in the database.

    :param study_id: The study_id (uuid) of the study.
    :param user_id: The ID of the user.
    :return: The generated auth_key.
    """
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_id)
    doc_ref_dict: dict = (await doc_ref.get()).to_dict()

    auth_key = secrets.token_hex(16)
    doc_ref_dict["personal_parameters"][user_id]["AUTH_KEY"]["value"] = auth_key
    await doc_ref.set(doc_ref_dict)

    await current_app.config["DATABASE"].collection("users").document("auth_keys").set(
        {
            auth_key: {
                "study_id": study_id,
                "username": user_id,
            }
        },
        merge=True,
    )

    return auth_key


async def setup_gcp(doc_ref: DocumentReference, role: str) -> None:
    await generate_ports(doc_ref, role)

    doc_ref_dict = (await doc_ref.get()).to_dict() or {}
    study_id = doc_ref_dict["study_id"]
    user: str = doc_ref_dict["participants"][int(role)]
    user_parameters: dict = doc_ref_dict["personal_parameters"][user]

    if "tasks" not in doc_ref_dict:
        doc_ref_dict["tasks"] = {}
    if user not in doc_ref_dict["tasks"]:
        doc_ref_dict["tasks"][user] = []
    doc_ref_dict["tasks"][user].append("Setting up networking and creating VM instance")
    await doc_ref.set(doc_ref_dict)

    gcloudCompute = GoogleCloudCompute(
        study_id, user_parameters["GCP_PROJECT"]["value"]
    )

    try:
        gcloudCompute.setup_networking(doc_ref_dict, role)

        metadata = [
            {
                "key": "data_path",
                "value": sanitize_path(user_parameters["DATA_PATH"]["value"]),
            },
            {
                "key": "geno_binary_file_prefix",
                "value": user_parameters["GENO_BINARY_FILE_PREFIX"]["value"],
            },
            {"key": "ports", "value": user_parameters["PORTS"]["value"]},
            {"key": "auth_key", "value": user_parameters["AUTH_KEY"]["value"]},
            {"key": "demo", "value": doc_ref_dict["demo"]},
        ]

        gcloudCompute.setup_instance(
            name=format_instance_name(doc_ref_dict["study_id"], role),
            role=role,
            metadata=metadata,
            num_cpus=int(user_parameters["NUM_CPUS"]["value"]),
            boot_disk_size=int(user_parameters["BOOT_DISK_SIZE"]["value"]),
        )
    except Exception as e:
        logger.error(f"An error occurred during GCP setup: {e}")
        doc_ref_dict["status"][
            user
        ] = "FAILED - sfkit failed to set up your networking and VM instance. Please restart the study and double-check your parameters and configuration. If the problem persists, please contact us."
        await doc_ref.set(doc_ref_dict)
        return
    else:
        doc_ref_dict = (await doc_ref.get()).to_dict() or {}
        doc_ref_dict["tasks"][user].append("Configuring your VM instance")
        await doc_ref.set(doc_ref_dict)
        return


async def _terra_rawls_post(path: str, json: Dict[str, Any]):
    async with httpx.AsyncClient() as http:
        res = await http.post(
            f"{constants.RAWLS_API_URL}/api/workspaces/{constants.TERRA_CP0_WORKSPACE_NAMESPACE}/{constants.TERRA_CP0_WORKSPACE_NAME}{path}",
            get_service_account_headers(),
            json=json,
        )
        if res.status_code != HTTPStatus.CREATED.value:
            raise HTTPException(response=res)


async def submit_terra_workflow(study_id: str, _role: str) -> None:
    # Add study ID to the data table:
    # https://rawls.dsde-dev.broadinstitute.org/#/entities/create_entity
    await _terra_rawls_post(
        "/entities",
        {
            "entityType": "study",
            "name": study_id,
            "attributes": {
                # add role if ever we need to use this for non-CP0
            },
        },
    )

    # Submit workflow for execution, referencing the study ID from the data table:
    # https://rawls.dsde-dev.broadinstitute.org/#/submissions/createSubmission
    await _terra_rawls_post(
        "/submissions",
        {
            "entityType": "study",
            "entityName": study_id,
            "methodConfigurationNamespace": constants.TERRA_CP0_CONFIG_NAMESPACE,
            "methodConfigurationName": constants.TERRA_CP0_CONFIG_NAME,
        },
    )


async def generate_ports(doc_ref: DocumentReference, role: str) -> None:
    doc_ref_dict = (await doc_ref.get()).to_dict() or {}
    user: str = doc_ref_dict["participants"][int(role)]

    base: int = 8000 + 200 * int(role)
    ports = [base + 20 * r for r in range(len(doc_ref_dict["participants"]))]
    ports = ",".join([str(p) for p in ports])

    doc_ref_dict["personal_parameters"][user]["PORTS"]["value"] = ports
    await doc_ref.set(doc_ref_dict, merge=True)


def add_file_to_zip(
    zip_file, filepath: str, archive_name: Optional[str] = None
) -> None:
    with open(filepath, "rb") as f:
        zip_file.writestr(archive_name or os.path.basename(filepath), f.read())


def sanitize_path(path: str) -> str:
    # remove trailing slash if present
    if path and path[-1] == "/":
        path = path[:-1]
    return path


def is_developer() -> bool:
    return (
        constants.FLASK_DEBUG == "development"
        and g.user
        and "id" in g.user
        and g.user["id"] == constants.DEVELOPER_USER_ID
    )


def is_participant(study) -> bool:
    return (
        g.user
        and "id" in g.user
        and (
            g.user["id"] in study["participants"]
            or g.user["id"] in study.get("invited_participants", [])
        )
    )


async def is_study_title_unique(study_title: str, db) -> bool:
    study_ref = (
        db.collection("studies").where("title", "==", study_title).limit(1).stream()
    )
    async for _ in study_ref:
        return False
    return True


# async def valid_study_title(
#     study_title: str, study_type: str, setup_configuration: str
# ) -> tuple[str, Response]:
#     # sourcery skip: assign-if-exp, reintroduce-else, swap-if-else-branches, use-named-expression
#     cleaned_study_title = await clean_study_title(study_title)

#     if not cleaned_study_title:
#         return (
#             "",
#             jsonify(
#                 {
#                     "message": "Title processing failed. Please add letters and try again.",
#                     "redirect_url": url_for(
#                         "studies.create_study",
#                         study_type=study_type,
#                         setup_configuration=setup_configuration,
#                     ),
#                 }
#             ),
#             400,  # Bad Request
#         )

#     if not await is_study_title_unique(
#         cleaned_study_title, current_app.config["DATABASE"]
#     ):
#         return (
#             "",
#             jsonify(
#                 {
#                     "message": "Title processing failed. Entered title is either a duplicate or too similar to an existing one.",
#                     "redirect_url": url_for(
#                         "studies.create_study",
#                         study_type=study_type,
#                         setup_configuration=setup_configuration,
#                     ),
#                 }
#             ),
#             400,  # Bad Request
#         )

#     return (
#         cleaned_study_title,
#         jsonify(
#             {
#                 "message": "Title processed successfully",
#                 "study_title": cleaned_study_title,
#             }
#         ),
#         200,
#     )  # OK


# async def clean_study_title(s: str) -> str:
#     # input_string = "123abc-!@#$%^&*() def" # Output: "abc- def"

#     # Remove all characters that don't match the pattern
#     cleaned_str = re.sub(r"[^a-zA-Z0-9-]", "", s)

#     # If the first character is not an alphabet, remove it
#     while len(cleaned_str) > 0 and not cleaned_str[0].isalpha():
#         cleaned_str = cleaned_str[1:]

#     return cleaned_str.lower()


def check_conditions(doc_ref_dict, user_id) -> str:
    # sourcery skip: assign-if-exp, reintroduce-else, swap-if-expression
    participants = doc_ref_dict["participants"]
    num_inds = doc_ref_dict["personal_parameters"][user_id]["NUM_INDS"]["value"]
    gcp_project = doc_ref_dict["personal_parameters"][user_id]["GCP_PROJECT"]["value"]
    data_path = doc_ref_dict["personal_parameters"][user_id]["DATA_PATH"]["value"]
    demo = doc_ref_dict["demo"]

    if not demo and len(participants) < 3:
        return "Non-demo studies require at least 2 participants to run the protocol."
    if not demo and not num_inds:
        return "You have not set the number of individuals/rows in your data. Please click on the 'Study Parameters' button to set this value and any other parameters you wish to change before running the protocol."
    if not gcp_project:
        return "Your GCP project ID is not set. Please follow the instructions in the 'Configure Study' button before running the protocol."
    if (
        not demo
        and "broad-cho-priv1" in gcp_project
        and constants.FLASK_DEBUG != "development"
    ):
        return "This project ID is only allowed for a demo study. Please follow the instructions in the 'Configure Study' button to set up your own GCP project before running the protocol."
    if not demo and not data_path:
        return "Your data path is not set. Please follow the instructions in the 'Configure Study' button before running the protocol."
    if not GoogleCloudIAM().test_permissions(gcp_project):
        return "You have not given the website the necessary GCP permissions for the project you have entered. Please click on 'Configure Study' to double-check that your project ID is correct and that you have given the website the necessary permissions (and they are not expired) in that GCP project."
    return ""


async def update_status_and_start_setup(doc_ref, doc_ref_dict, study_id):
    participants = doc_ref_dict["participants"]
    statuses = doc_ref_dict["status"]

    for role in range(1, len(participants)):
        user = participants[role]
        statuses[user] = "setting up your vm instance"
        await doc_ref.set({"status": statuses}, merge=True)

        await make_auth_key(study_id, user)

        asyncio.create_task(setup_gcp(doc_ref, str(role)))

        time.sleep(1)
