import os
import re
import secrets
from typing import Optional

from flask import current_app, g, redirect, url_for
from google.cloud.firestore_v1 import DocumentReference
from python_http_client.exceptions import HTTPError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail
from werkzeug import Response

from src.utils import constants
from src.utils.generic_functions import redirect_with_flash
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute, create_instance_name


def email(inviter: str, recipient: str, invitation_message: str, study_title: str) -> int:
    doc_ref_dict: dict = current_app.config["DATABASE"].collection("meta").document("sendgrid").get().to_dict()
    sg = SendGridAPIClient(api_key=doc_ref_dict.get("api_key", ""))

    html_content = f"<p>Hello!<br>{inviter} has invited you to join the {study_title} study on the sfkit website.  Click <a href='https://sfkit.org/accept_invitation/{study_title.replace(' ', '').lower()}'>here</a> to accept the invitation. (Note: you will need to log in using this email address to accept the invitation.)"

    if invitation_message:
        html_content += f"<br><br>Here is a message from {inviter}:<br>{invitation_message}"
    html_content += "</p>"

    message = Mail(
        to_emails=recipient,
        from_email=Email(doc_ref_dict.get("from_email", ""), doc_ref_dict.get("from_user", "")),
        subject=f"sfkit: Invitation to join {study_title} study",
        html_content=html_content,
    )
    message.add_bcc(doc_ref_dict.get("from_email", ""))

    try:
        response = sg.send(message)
        print("Email sent")
        return response.status_code  # type: ignore

    except HTTPError as e:  # type: ignore
        print("Email failed to send", e)
        return e.status_code  # type: ignore


def make_auth_key(study_title: str, user_id: str) -> str:
    """
    Make auth_key.txt file for user
    """
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()

    auth_key = secrets.token_hex(16)
    doc_ref_dict["personal_parameters"][user_id]["AUTH_KEY"]["value"] = auth_key
    doc_ref.set(doc_ref_dict)

    current_app.config["DATABASE"].collection("users").document("auth_keys").set(
        {
            auth_key: {
                "study_title": study_title,
                "username": user_id,
            }
        },
        merge=True,
    )

    return auth_key


def setup_gcp(doc_ref: DocumentReference, role: str) -> None:
    generate_ports(doc_ref, role)

    doc_ref_dict = doc_ref.get().to_dict() or {}
    study_title = doc_ref_dict["title"].replace(" ", "").lower()
    user: str = doc_ref_dict["participants"][int(role)]
    user_parameters: dict = doc_ref_dict["personal_parameters"][user]

    if "tasks" not in doc_ref_dict:
        doc_ref_dict["tasks"] = {}
    if user not in doc_ref_dict["tasks"]:
        doc_ref_dict["tasks"][user] = []
    doc_ref_dict["tasks"][user].append("Setting up networking and creating VM instance")
    doc_ref.set(doc_ref_dict)

    gcloudCompute = GoogleCloudCompute(study_title, user_parameters["GCP_PROJECT"]["value"])

    try:
        gcloudCompute.setup_networking(doc_ref_dict, role)

        metadata = [
            {"key": "data_path", "value": sanitize_path(user_parameters["DATA_PATH"]["value"])},
            {"key": "geno_binary_file_prefix", "value": user_parameters["GENO_BINARY_FILE_PREFIX"]["value"]},
            {"key": "ports", "value": user_parameters["PORTS"]["value"]},
            {"key": "auth_key", "value": user_parameters["AUTH_KEY"]["value"]},
            {"key": "demo", "value": doc_ref_dict["demo"]},
        ]

        gcloudCompute.setup_instance(
            name=create_instance_name(doc_ref_dict["title"], role),
            role=role,
            metadata=metadata,
            num_cpus=int(user_parameters["NUM_CPUS"]["value"]),
            boot_disk_size=int(user_parameters["BOOT_DISK_SIZE"]["value"]),
        )
    except Exception as e:
        print(e)
        doc_ref_dict["status"][
            user
        ] = "FAILED - sfkit failed to set up your networking and VM instance. Please restart the study and double-check your parameters and configuration. If the problem persists, please contact us."
        doc_ref.set(doc_ref_dict)
        return
    else:
        doc_ref_dict = doc_ref.get().to_dict() or {}
        if doc_ref_dict["tasks"][user][-1] == "Setting up networking and creating VM instance":
            doc_ref_dict["tasks"][user][-1] += " completed"
        doc_ref_dict["tasks"][user].append("Configuring your VM instance")
        doc_ref.set(doc_ref_dict)
        return


def generate_ports(doc_ref: DocumentReference, role: str) -> None:
    doc_ref_dict = doc_ref.get().to_dict() or {}
    user: str = doc_ref_dict["participants"][int(role)]

    base: int = 8000 + 200 * int(role)
    ports = [base + 20 * r for r in range(len(doc_ref_dict["participants"]))]
    ports = ",".join([str(p) for p in ports])

    doc_ref_dict["personal_parameters"][user]["PORTS"]["value"] = ports
    doc_ref.set(doc_ref_dict, merge=True)


def add_file_to_zip(zip_file, filepath: str, archive_name: Optional[str] = None) -> None:
    with open(filepath, "rb") as f:
        zip_file.writestr(archive_name or os.path.basename(filepath), f.read())


def sanitize_path(path: str) -> str:
    # remove trailing slash if present
    if path and path[-1] == "/":
        path = path[:-1]
    return path


def is_developer() -> bool:
    return (
        os.environ.get("FLASK_DEBUG") == "development"
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


def valid_study_title(study_title: str, study_type: str, setup_configuration: str) -> tuple[str, Response]:
    cleaned_study_title = clean_study_title(study_title)

    if not cleaned_study_title:
        return (
            "",
            redirect_with_flash(
                url=url_for("studies.create_study", study_type=study_type, setup_configuration=setup_configuration),
                message="Failed to process title.  Please add letters and try again.",
            ),
        )

    # validate that title is unique
    db = current_app.config["DATABASE"]
    studies = db.collection("studies").stream()
    for study in studies:
        if study.to_dict()["title"] == cleaned_study_title:
            return (
                "",
                redirect_with_flash(
                    url=url_for(
                        "studies.create_study", study_type=study_type, setup_configuration=setup_configuration
                    ),
                    message="Title already exists.",
                ),
            )

    return (cleaned_study_title, redirect(url_for("studies.parameters", study_title=cleaned_study_title)))


def clean_study_title(s: str) -> str:
    # input_string = "123abc-!@#$%^&*() def" # Output: "abc- def"

    # Remove all characters that don't match the pattern
    cleaned_str = re.sub(r"[^a-zA-Z0-9-]", "", s)

    # If the first character is not an alphabet, remove it
    while len(cleaned_str) > 0 and not cleaned_str[0].isalpha():
        cleaned_str = cleaned_str[1:]

    return cleaned_str.lower()
