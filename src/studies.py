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
from src.utils.google_cloud.google_cloud_pubsub import GoogleCloudPubsub
from src.utils.gwas_functions import valid_study_title

bp = Blueprint("studies", __name__)


@bp.route("/index")
def index() -> Response:
    db = current_app.config["DATABASE"]
    studies = db.collection("studies")
    studies_list = [study.to_dict() for study in studies.stream()]
    return make_response(render_template("studies/index.html", studies=studies_list))


@bp.route("/study/<study_title>", methods=("GET", "POST"))
@login_required
def study(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    public_keys = [
        doc_ref_dict["personal_parameters"][user]["PUBLIC_KEY"]["value"] for user in doc_ref_dict["participants"]
    ]
    user_id = g.user["id"]
    role: int = doc_ref_dict["participants"].index(user_id)

    return make_response(
        render_template(
            "studies/study/study.html",
            study=doc_ref_dict,
            public_keys=public_keys,
            role=role,
            study_type=doc_ref_dict["study_type"],
            parameters=doc_ref_dict["personal_parameters"][user_id],
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
    return redirect(url_for("studies.create_study", study_type=study_type))


@bp.route("/create_study/<study_type>", methods=("GET", "POST"))
@login_required
def create_study(study_type: str) -> Response:
    if request.method == "GET":
        return make_response(render_template("studies/create_study.html", study_type=study_type))

    db = current_app.config["DATABASE"]
    title = request.form["title"]
    description = request.form["description"]
    study_information = request.form["study_information"]

    (valid, response) = valid_study_title(title, study_type)
    if not valid:
        return response

    doc_ref = db.collection("studies").document(title.replace(" ", "").lower())
    doc_ref.set(
        {
            "title": title,
            "study_type": study_type,
            "private": request.form.get("private_study") == "on",
            "description": description,
            "study_information": study_information,
            "owner": g.user["id"],
            "created": datetime.now(),
            "participants": ["Broad", g.user["id"]],
            "status": {"Broad": ["ready"], g.user["id"]: [""]},
            "parameters": constants.SHARED_PARAMETERS[study_type],
            "personal_parameters": {
                "Broad": constants.broad_user_parameters(),
                g.user["id"]: constants.default_user_parameters(study_type),
            },
            "requested_participants": [],
            "invited_participants": [],
        }
    )

    # add pubsub topic for this user and for cp0
    # gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, "0", title)
    # gcloudPubsub.create_topic_and_subscribe()
    # gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, "1", title)
    # gcloudPubsub.create_topic_and_subscribe()

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

    # delete pubsub topics, subscriptions and service accounts
    for role, _ in enumerate(doc_ref_dict["participants"]):
        google_cloud_pubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, str(role), study_title)
        google_cloud_pubsub.delete_topics_and_subscriptions()

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
    invitee: str = request.form["invite_participant_email"]
    email(invitee, study_title)

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["invited_participants"].append(invitee)
    doc_ref.set(
        {"invited_participants": doc_ref_dict["invited_participants"]},
        merge=True,
    )
    return redirect(url_for("studies.study", study_title=study_title))


def email(recipient: str, study_title: str) -> str:
    doc_ref_dict: dict = current_app.config["DATABASE"].collection("meta").document("sendgrid").get().to_dict()

    sg = SendGridAPIClient(api_key=doc_ref_dict["api_key"])

    html_content = f"<p>Hello!<br>You have been invited to join the {study_title} study on the Secure GWAS website.  Click <a href='https://secure-gwas-website-bhj5a4wkqa-uc.a.run.app/accept_invitation/{study_title.replace(' ', '').lower()}'>here</a> to accept the invitation.</p>"

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
        return f"email.status_code={response.status_code}"
        # expected 202 Accepted

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

    # TODO: when do we need this pubsub?
    # add pubsub topic for this user for this study
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, "2", study_title)
    gcloudPubsub.create_topic_and_subscribe()

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

    # add pubsub topic for this user for this study
    # gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, "2", study_title)
    # gcloudPubsub.create_topic_and_subscribe()

    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/parameters/<study_title>", methods=("GET", "POST"))
@login_required
def parameters(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    parameters = doc_ref_dict.get("parameters")
    if request.method == "GET":
        return make_response(
            render_template(
                "studies/parameters.html",
                study=doc_ref_dict,
            )
        )
    elif "save" in request.form:
        for p in parameters["index"]:
            parameters[p]["value"] = request.form.get(p)
        doc_ref.set({"parameters": parameters}, merge=True)
        return redirect(url_for("studies.study", study_title=study_title))
    else:
        return redirect_with_flash(
            url=url_for("studies.parameters", study_title=study_title),
            message="Something went wrong. Please try again.",
        )


@bp.route("/personal_parameters/<study_title>", methods=("GET", "POST"))
def personal_parameters(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    parameters = doc_ref.get().to_dict().get("personal_parameters")

    # if request.method == "GET":
    #     return render_template(
    #         "studies/personal_parameters.html",
    #         study_title=study_title,
    #         parameters=parameters[g.user["id"]],
    #     )

    for p in parameters[g.user["id"]]["index"]:
        if p in request.form:
            parameters[g.user["id"]][p]["value"] = request.form.get(p)
    doc_ref.set({"personal_parameters": parameters}, merge=True)
    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/study/<study_title>/choose_workflow", methods=("POST",))
@login_required
def choose_workflow(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["personal_parameters"][g.user["id"]]["CONFIGURE_STUDY_GCP_SETUP_MODE"]["value"] = request.form.get(
        "CONFIGURE_STUDY_GCP_SETUP_MODE"
    )
    doc_ref.set(doc_ref_dict)
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


# @bp.route("/study/<study_title>/download_sa_key_file", methods=("GET",))
# @login_required
# def download_sa_key_file(study_title: str) -> Response:
#     db = current_app.config["DATABASE"]
#     doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
#     doc_ref_dict = doc_ref.get().to_dict()

#     sa_email, json_sa_key = setup_service_account_and_key(study_title, g.user["id"])
#     doc_ref_dict["personal_parameters"][g.user["id"]]["SA_EMAIL"]["value"] = sa_email
#     doc_ref.set(doc_ref_dict)
#     key_file = io.BytesIO(json_sa_key.encode("utf-8"))
#     return send_file(
#         key_file,
#         download_name="sa_key.json",
#         mimetype="text/plain",
#         as_attachment=True,
#     )
