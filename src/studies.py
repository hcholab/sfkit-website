import secrets
import io
from datetime import datetime

from flask import Blueprint, current_app, g, make_response, redirect, render_template, request, send_file, url_for
from python_http_client.exceptions import HTTPError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail
from werkzeug import Response

from src.auth import login_required
from src.utils import constants
from src.utils.generic_functions import add_notification, redirect_with_flash
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM
from src.utils.gwas_functions import create_instance_name, valid_study_title

bp = Blueprint("studies", __name__)


@bp.route("/index")
def index() -> Response:
    db = current_app.config["DATABASE"]
    studies = db.collection("studies")
    studies_list = [study.to_dict() for study in studies.stream()]

    display_names = db.collection("users").document("display_names").get().to_dict()

    return make_response(render_template("studies/index.html", studies=studies_list, display_names=display_names))


@bp.route("/study/<study_title>", methods=("GET", "POST"))
@login_required
def study(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    user_id = g.user["id"]
    role: int = doc_ref_dict["participants"].index(user_id)

    display_names = db.collection("users").document("display_names").get().to_dict()

    return make_response(
        render_template(
            "studies/study/study.html",
            study=doc_ref_dict,
            role=role,
            study_type=doc_ref_dict["study_type"],
            parameters=doc_ref_dict["personal_parameters"][user_id],
            display_names=display_names,
        )
    )


@bp.route("/study/<study_title>/download_public_key/<role>")
@login_required
def download_public_key(study_title: str, role: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    user_id = doc_ref_dict["participants"][int(role)]
    public_key = doc_ref_dict["personal_parameters"][user_id]["PUBLIC_KEY"]["value"]
    key_file = io.BytesIO(public_key.encode("utf-8") + b"\n" + role.encode("utf-8"))
    return send_file(
        key_file,
        download_name=f"public_key_{user_id}.txt",
        mimetype="text/plain",
        as_attachment=True,
    )


@bp.route("/study/<study_title>/upload_public_key", methods=("GET", "POST"))
@login_required
def upload_public_key(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    file = request.files["file"]
    if file.filename == "":
        return redirect_with_flash(
            url=url_for("studies.study", study_title=study_title),
            message="Please select a file to upload.",
        )
    elif file and file.filename == "my_public_key.txt":
        public_key = file.read().decode("utf-8")
        doc_ref_dict["personal_parameters"][g.user["id"]]["PUBLIC_KEY"]["value"] = public_key
        doc_ref.set(doc_ref_dict)
        return redirect(url_for("studies.study", study_title=study_title))
    else:
        return redirect_with_flash(
            url=url_for("studies.study", study_title=study_title),
            message="Please upload a valid my_public_key.txt file.",
        )


@bp.route("/choose_study_type", methods=["POST"])
@login_required
def choose_study_type() -> Response:
    study_type = request.form["CHOOSE_STUDY_TYPE"]
    setup_configuration: str = request.form["SETUP_CONFIGURATION"]
    return redirect(url_for("studies.create_study", study_type=study_type, setup_configuration=setup_configuration))


@bp.route("/create_study/<study_type>/<setup_configuration>", methods=("GET", "POST"))
@login_required
def create_study(study_type: str, setup_configuration: str) -> Response:
    if request.method == "GET":
        return make_response(render_template("studies/create_study.html", study_type=study_type))

    title = request.form["title"]
    description = request.form["description"]
    study_information = request.form["study_information"]

    (valid, response) = valid_study_title(title, study_type)
    if not valid:
        return response

    doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
    doc_ref.set(
        {
            "title": title,
            "study_type": study_type,
            "setup_configuration": setup_configuration,
            "private": request.form.get("private_study") == "on",
            "description": description,
            "study_information": study_information,
            "owner": g.user["id"],
            "created": datetime.now(),
            "participants": ["Broad", g.user["id"]],
            "status": {"Broad": [""], g.user["id"]: [""]},
            "parameters": constants.SHARED_PARAMETERS[study_type],
            "advanced_parameters": constants.ADVANCED_PARAMETERS[study_type],
            "personal_parameters": {
                "Broad": constants.broad_user_parameters(),
                g.user["id"]: constants.default_user_parameters(study_type),
            },
            "requested_participants": [],
            "invited_participants": [],
        }
    )

    make_auth_key(title, "Broad")  # make auth_key for cp0

    return response


@bp.route("/delete_study/<study_title>", methods=("POST",))
@login_required
def delete_study(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()

    # delete vms that may still exist
    google_cloud_compute = GoogleCloudCompute("")
    for participant in doc_ref_dict["personal_parameters"].values():
        if (gcp_project := participant.get("GCP_PROJECT").get("value")) != "":
            google_cloud_compute.project = gcp_project
            for instance in google_cloud_compute.list_instances():
                if constants.INSTANCE_NAME_ROOT in instance and study_title in instance:
                    google_cloud_compute.delete_instance(instance)

    doc_ref.delete()
    return redirect(url_for("studies.index"))


@bp.route("/request_join_study/<study_title>")
@login_required
def request_join_study(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["requested_participants"].append(g.user["id"])
    doc_ref.set(
        {"requested_participants": doc_ref_dict["requested_participants"]},
        merge=True,
    )
    return redirect(url_for("studies.index"))


@bp.route("/invite_participant/<study_title>", methods=["POST"])
@login_required
def invite_participant(study_title: str) -> Response:
    inviter: str = g.user["id"]
    invitee: str = request.form["invite_participant_email"]
    message: str = request.form.get("invite_participant_message", "")
    email(inviter, invitee, message, study_title)

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["invited_participants"].append(invitee)
    doc_ref.set(
        {"invited_participants": doc_ref_dict["invited_participants"]},
        merge=True,
    )
    return redirect(url_for("studies.study", study_title=study_title))


def email(inviter: str, recipient: str, invitation_message: str, study_title: str) -> str:
    doc_ref_dict: dict = current_app.config["DATABASE"].collection("meta").document("sendgrid").get().to_dict()
    sg = SendGridAPIClient(api_key=doc_ref_dict["api_key"])

    html_content = f"<p>Hello!<br>{inviter} has invited you to join the {study_title} study on the Secure GWAS website.  Click <a href='https://secure-gwas-website-bhj5a4wkqa-uc.a.run.app/accept_invitation/{study_title.replace(' ', '').lower()}'>here</a> to accept the invitation."

    if invitation_message:
        html_content += f"<br><br>Here is a message from {inviter}:<br>{invitation_message}</p>"
    html_content += "</p>"

    message = Mail(
        to_emails=recipient,
        from_email=Email(doc_ref_dict["from_email"], doc_ref_dict["from_user"]),
        subject=f"sfkit: Invitation to join {study_title} study",
        html_content=html_content,
    )
    message.add_bcc(doc_ref_dict["from_email"])

    try:
        response = sg.send(message)
        print("Email sent")
        return f"email.status_code={response.status_code}"  # expected 202 Accepted

    except HTTPError as e:
        print("Email failed to send", e)
        return f"email.status_code={e.status_code}"


@bp.route("/approve_join_study/<study_title>/<user_id>")
@login_required
def approve_join_study(study_title: str, user_id: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()

    doc_ref.set(
        {
            "requested_participants": doc_ref_dict["requested_participants"].remove(user_id),
            "participants": doc_ref_dict["participants"] + [user_id],
            "personal_parameters": doc_ref_dict["personal_parameters"]
            | {user_id: constants.default_user_parameters(doc_ref_dict["study_type"])},
            "status": doc_ref_dict["status"] | {user_id: [""]},
        },
        merge=True,
    )

    add_notification(f"You have been accepted to {study_title}", user_id=user_id)
    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/accept_invitation/<study_title>", methods=["GET", "POST"])
@login_required
def accept_invitation(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()

    doc_ref.set(
        {
            "invited_participants": doc_ref_dict["invited_participants"].remove(g.user["id"]),
            "participants": doc_ref_dict["participants"] + [g.user["id"]],
            "personal_parameters": doc_ref_dict["personal_parameters"]
            | {g.user["id"]: constants.default_user_parameters(doc_ref_dict["study_type"])},
            "status": doc_ref_dict["status"] | {g.user["id"]: [""]},
        },
        merge=True,
    )

    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/study/<study_title>/study_information", methods=["POST"])
@login_required
def study_information(study_title: str) -> Response:
    doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title.replace(" ", "").lower())

    doc_ref.set(
        {
            "description": request.form["study_description"],
            "study_information": request.form["study_information"],
        },
        merge=True,
    )

    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/parameters/<study_title>", methods=("GET", "POST"))
@login_required
def parameters(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    if request.method == "GET":
        return make_response(
            render_template(
                "studies/parameters.html",
                study=doc_ref_dict,
            )
        )
    for p in request.form:
        if p in doc_ref_dict["parameters"]["index"]:
            doc_ref_dict["parameters"][p]["value"] = request.form.get(p)
        elif p in doc_ref_dict["advanced_parameters"]["index"]:
            doc_ref_dict["advanced_parameters"][p]["value"] = request.form.get(p)
        elif "NUM_INDS" in p:
            participant = p.split("NUM_INDS")[1]
            doc_ref_dict["personal_parameters"][participant]["NUM_INDS"]["value"] = request.form.get(p)
    doc_ref.set(doc_ref_dict, merge=True)
    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/personal_parameters/<study_title>", methods=("GET", "POST"))
def personal_parameters(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    parameters = doc_ref.get().to_dict().get("personal_parameters")

    for p in parameters[g.user["id"]]["index"]:
        if p in request.form:
            parameters[g.user["id"]][p]["value"] = request.form.get(p)
    doc_ref.set({"personal_parameters": parameters}, merge=True)
    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/study/<study_title>/set_sa_email", methods=("POST",))
@login_required
def set_sa_email(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["personal_parameters"][g.user["id"]]["SA_EMAIL"]["value"] = request.form.get("SA_EMAIL")
    doc_ref.set(doc_ref_dict)
    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/study/<study_title>/download_key_file", methods=("GET",))
@login_required
def download_key_file(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    auth_key = doc_ref_dict["personal_parameters"][g.user["id"]]["AUTH_KEY"]["value"]

    if not auth_key:
        auth_key = make_auth_key(study_title, g.user["id"])

    return send_file(
        io.BytesIO(auth_key.encode()),
        download_name="auth_key.txt",
        mimetype="text/plain",
        as_attachment=True,
    )


def make_auth_key(study_title: str, user_id: str) -> str:
    """
    Make auth_key.txt file for user
    """
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()

    auth_key = secrets.token_hex(16)
    doc_ref_dict["personal_parameters"][user_id]["AUTH_KEY"]["value"] = auth_key
    doc_ref.set(doc_ref_dict)

    current_app.config["DATABASE"].collection("users").document("auth_keys").set(
        {
            auth_key: {
                "study_title": study_title,
                "user_email": user_id,
            }
        },
        merge=True,
    )

    return auth_key


@bp.route("/study/<study_title>/start_protocol", methods=["POST"])
@login_required
def start_protocol(study_title: str) -> Response:
    user_id: str = g.user["id"]
    doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()
    role: str = str(doc_ref_dict["participants"].index(user_id))
    gcp_project: str = doc_ref_dict["personal_parameters"][user_id]["GCP_PROJECT"]["value"]
    data_path: str = doc_ref_dict["personal_parameters"][user_id]["DATA_PATH"]["value"]
    statuses: dict = doc_ref_dict["status"]

    if statuses[user_id] == [""]:
        if not gcp_project:
            return redirect_with_flash(
                url=url_for("studies.study", study_title=study_title),
                message="Your GCP project ID is not set.  Please follow the instructions in the 'Configure Study' button before running the protocol.",
            )
        if not data_path:
            return redirect_with_flash(
                url=url_for("studies.study", study_title=study_title),
                message="Your data path is not set.  Please follow the instructions in the 'Configure Study' button before running the protocol.",
            )
        if not GoogleCloudIAM().test_permissions(gcp_project):
            return redirect_with_flash(
                location="general.permissions",
                message="Please give the service appropriate permissions first.",
            )

        statuses[user_id] = ["ready"]
        personal_parameters = doc_ref_dict["personal_parameters"]
        personal_parameters[user_id]["NUM_CPUS"]["value"] = request.form["NUM_CPUS"]
        personal_parameters[user_id]["NUM_THREADS"]["value"] = request.form["NUM_CPUS"]
        personal_parameters[user_id]["BOOT_DISK_SIZE"]["value"] = request.form["BOOT_DISK_SIZE"]
        doc_ref.set(
            {
                "status": statuses,
                "personal_parameters": personal_parameters,
            },
            merge=True,
        )

    if [""] in statuses.values():
        print("Not all participants are ready.")
    elif statuses[user_id] == ["ready"]:
        statuses[user_id] = ["Setting up your vm instance..."]
        doc_ref.set({"status": statuses}, merge=True)
        doc_ref_dict = doc_ref.get().to_dict()

        make_auth_key(study_title, user_id)
        setup_gcp(doc_ref_dict, role)

        if role == "1":
            setup_gcp(doc_ref_dict, "0")

    return redirect(url_for("studies.study", study_title=study_title))


def setup_gcp(doc_ref_dict: dict, role: str) -> None:
    user: str = doc_ref_dict["participants"][int(role)]
    user_parameters: dict = doc_ref_dict["personal_parameters"][user]
    gcloudCompute = GoogleCloudCompute(user_parameters["GCP_PROJECT"]["value"])
    gcloudCompute.setup_networking(doc_ref_dict, role)
    gcloudCompute.setup_instance(
        name=create_instance_name(doc_ref_dict["title"], role),
        role=role,
        metadata=[
            {"key": "data_path", "value": user_parameters["DATA_PATH"]["value"]},
            {"key": "geno_binary_file_prefix", "value": user_parameters["GENO_BINARY_FILE_PREFIX"]["value"]},
            {"key": "ports", "value": user_parameters["PORTS"]["value"]},
            {"key": "auth_key", "value": user_parameters["AUTH_KEY"]["value"]},
        ],
        num_cpus=user_parameters["NUM_CPUS"]["value"],
        boot_disk_size=user_parameters["BOOT_DISK_SIZE"]["value"],
    )
