import asyncio
import os
import secrets
import time
from html import escape
from http import HTTPStatus
from string import Template
from typing import Any, Dict

import httpx
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncDocumentReference, FieldFilter
from python_http_client.exceptions import HTTPError
from quart import current_app, g
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail
from werkzeug.exceptions import BadRequest

from src.api_utils import APIException, fetch_study
from src.auth import get_service_account_headers
from src.utils import constants, custom_logging
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute, format_instance_name
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM

logger = custom_logging.setup_logging(__name__)

email_template = Template(
    """
    <p>Hello!<br>${inviter} has invited you to join the ${study_title} study on the sfkit website. Sign-in on the website to accept the invitation!<br>${invitation_message}</p>
    """
)


async def email(inviter: str, recipient: str, invitation_message: str, study_title: str) -> int:
    """
    Sends an invitation email to the recipient.

    :param inviter: The name of the person inviting the recipient.
    :param recipient: The email address of the recipient.
    :param invitation_message: A custom message from the inviter.
    :param study_title: The title of the study the recipient is being invited to.
    :return: The status code of the email sending operation.
    """
    doc_ref_dict: dict = (await current_app.config["DATABASE"].collection("meta").document("sendgrid").get()).to_dict()

    api_key = os.getenv("SENDGRID_API_KEY") or doc_ref_dict.get("api_key")
    if not api_key:
        raise BadRequest("No SendGrid API key found")
    sg = SendGridAPIClient(api_key=api_key)

    html_content = email_template.substitute(
        inviter=escape(inviter),
        invitation_message=escape(invitation_message) if invitation_message else "",
        study_title=escape(study_title),
    )

    message = Mail(
        to_emails=recipient,
        from_email=Email(doc_ref_dict.get("from_email", ""), doc_ref_dict.get("from_user", "")),
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
    _, doc_ref, doc_ref_dict = await fetch_study(study_id, user_id)

    auth_key = secrets.token_hex(16)
    doc_ref_dict["personal_parameters"][user_id]["AUTH_KEY"]["value"] = auth_key
    await doc_ref.set(doc_ref_dict)

    await current_app.config["DATABASE"].collection("users").document("auth_keys").set(
        {
            auth_key: {
                "study_id": study_id,
                "title": doc_ref_dict["title"],
                "username": user_id,
            }
        },
        merge=True,
    )

    return auth_key


async def setup_gcp(doc_ref: AsyncDocumentReference, role: str) -> None:
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

    gcloudCompute = GoogleCloudCompute(study_id, user_parameters["GCP_PROJECT"]["value"])

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
            {"key": "study_type", "value": doc_ref_dict["study_type"]},
            {"key": "SFKIT_API_URL", "value": constants.SFKIT_API_URL},
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
        return await http.post(
            f"{constants.RAWLS_API_URL}/api/workspaces/{constants.TERRA_CP0_WORKSPACE_NAMESPACE}/{constants.TERRA_CP0_WORKSPACE_NAME}{path}",
            headers=get_service_account_headers(),
            json=json,
        )


async def submit_terra_workflow(study_id: str, _role: str) -> None:
    # Add study ID to the data table:
    # https://rawls.dsde-dev.broadinstitute.org/#/entities/create_entity
    res = await _terra_rawls_post(
        "/entities",
        {
            "entityType": "study",
            "name": study_id,
            "attributes": {
                # add role if ever we need to use this for non-CP0
            },
        },
    )
    if res.status_code not in (HTTPStatus.CREATED.value, HTTPStatus.CONFLICT.value):
        raise APIException(res)

    # Submit workflow for execution, referencing the study ID from the data table:
    # https://rawls.dsde-dev.broadinstitute.org/#/submissions/createSubmission
    res = await _terra_rawls_post(
        "/submissions",
        {
            "entityType": "study",
            "entityName": study_id,
            "methodConfigurationNamespace": constants.TERRA_CP0_CONFIG_NAMESPACE,
            "methodConfigurationName": constants.TERRA_CP0_CONFIG_NAME,
            "useCallCache": False,
        },
    )
    if res.status_code != HTTPStatus.CREATED.value:
        raise APIException(res)


async def generate_ports(doc_ref: AsyncDocumentReference, role: str) -> None:
    doc_ref_dict = (await doc_ref.get()).to_dict() or {}
    user: str = doc_ref_dict["participants"][int(role)]

    base: int = 8000 + 200 * int(role)
    ports = [base + 20 * r for r in range(len(doc_ref_dict["participants"]))]
    ports_str = ",".join([str(p) for p in ports])

    doc_ref_dict["personal_parameters"][user]["PORTS"]["value"] = ports_str
    await doc_ref.set(doc_ref_dict, merge=True)


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
        and (g.user["id"] in study["participants"] or g.user["id"] in study.get("invited_participants", []))
    )


async def is_study_title_unique(study_title: str, db) -> bool:
    study_ref = db.collection("studies").where("title", "==", study_title).limit(1).stream()
    async for _ in study_ref:
        return False
    return True


async def study_title_already_exists(study_title: str) -> bool:
    logger.info(f"Checking if study title {study_title} already exists")
    db: firestore.AsyncClient = current_app.config["DATABASE"]
    study_ref = db.collection("studies").where(filter=FieldFilter("title", "==", study_title)).limit(1).stream()
    async for _ in study_ref:
        return True
    return False


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
    if not demo and "broad-cho-priv1" in gcp_project and constants.FLASK_DEBUG != "development":
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

        asyncio.create_task(setup_gcp(doc_ref, str(role)))

        time.sleep(1)
