import io
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    g,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug import Response

from src.auth import login_required
from src.utils import constants
from src.utils.generic_functions import add_notification, redirect_with_flash
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
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
    role: int = doc_ref_dict["participants"].index(user_id) + 1

    return make_response(
        render_template(
            "studies/study.html",
            study=doc_ref_dict,
            public_keys=public_keys,
            role=role,
            type=doc_ref_dict["type"],
            parameters=doc_ref_dict["personal_parameters"][user_id],
        )
    )


@bp.route("/study/<study_title>/download_public_key/<role>")
@login_required
def download_public_key(study_title: str, role: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    user_id = doc_ref_dict["participants"][int(role) - 1]
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


@bp.route("/create_study/<type>", methods=("GET", "POST"))
@login_required
def create_study(type: str) -> Response:
    if request.method == "GET":
        return make_response(render_template("studies/create_study.html", type=type))

    db = current_app.config["DATABASE"]
    title = request.form["title"]
    description = request.form["description"]
    study_information = request.form["study_information"]

    (valid, response) = valid_study_title(title, type)
    if not valid:
        return response

    doc_ref = db.collection("studies").document(title.replace(" ", "").lower())
    doc_ref.set(
        {
            "title": title,
            "type": type,
            "description": description,
            "study_information": study_information,
            "owner": g.user["id"],
            "created": datetime.now(),
            "participants": [g.user["id"]],
            "status": {g.user["id"]: [""]},
            "parameters": constants.get_shared_parameters(type),
            "personal_parameters": {g.user["id"]: constants.DEFAULT_USER_PARAMETERS},
            "requested_participants": [],
        }
    )
    return response


@bp.route("/delete_study/<study_title>", methods=("POST",))
@login_required
def delete_study(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()

    # delete vms that may still exist
    google_cloud_compute = GoogleCloudCompute("")  # TODO: delete the server's VM as well
    for participant in doc_ref_dict["personal_parameters"].values():
        if (gcp_project := participant.get("GCP_PROJECT").get("value")) != "":
            google_cloud_compute.project = gcp_project
            for instance in google_cloud_compute.list_instances():
                if constants.INSTANCE_NAME_ROOT in instance:
                    google_cloud_compute.delete_instance(instance)

    doc_ref.delete()
    return redirect(url_for("studies.index"))


@bp.route("/request_join_study/<study_title>")
@login_required
def request_join_study(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["requested_participants"] = [g.user["id"]]
    doc_ref.set(
        {"requested_participants": doc_ref_dict["requested_participants"]},
        merge=True,
    )
    return redirect(url_for("studies.index"))


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
            "personal_parameters": doc_ref_dict["personal_parameters"] | {user_id: constants.DEFAULT_USER_PARAMETERS},
            "status": doc_ref_dict["status"] | {user_id: [""]},
        },
        merge=True,
    )

    add_notification(f"You have been accepted to {study_title}", user_id=user_id)

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
def personal_parameters(study_title):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    parameters = doc_ref.get().to_dict().get("personal_parameters")

    if request.method == "GET":
        return render_template(
            "studies/personal_parameters.html",
            study_title=study_title,
            parameters=parameters[g.user["id"]],
        )

    for p in parameters[g.user["id"]]["index"]:
        if p in request.form:
            parameters[g.user["id"]][p]["value"] = request.form.get(p)
    doc_ref.set({"personal_parameters": parameters}, merge=True)
    return redirect(url_for("studies.study", study_title=study_title))
