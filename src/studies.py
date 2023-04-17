import io
import os
import time
import zipfile
from datetime import datetime
from threading import Thread

from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from google.cloud import firestore
from werkzeug import Response

from src.auth import login_required
from src.utils import constants
from src.utils.auth_functions import create_user, update_user
from src.utils.generic_functions import add_notification, redirect_with_flash
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute, create_instance_name
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM
from src.utils.google_cloud.google_cloud_storage import download_blob_to_filename
from src.utils.gwas_functions import valid_study_title
from src.utils.studies_functions import add_file_to_zip, email, is_developer, is_participant, make_auth_key, setup_gcp

bp = Blueprint("studies", __name__)


@bp.route("/index", methods=["GET"])
def index() -> Response:
    db = current_app.config["DATABASE"]
    studies = db.collection("studies")
    all_studies: list[dict] = [study.to_dict() for study in studies.stream()]
    my_studies: list = []
    other_studies: list = []

    for study in all_studies:
        if is_developer() or is_participant(study):
            my_studies.append(study)
        elif not study["private"]:
            other_studies.append(study)

    display_names: dict = db.collection("users").document("display_names").get().to_dict()

    return make_response(
        render_template(
            "studies/index.html",
            studies=all_studies,
            my_studies=my_studies,
            other_studies=other_studies,
            display_names=display_names,
        )
    )


@bp.route("/study/<study_title>", methods=("GET", "POST"))
@login_required
def study(study_title: str) -> Response:
    study_title = study_title.replace(" ", "").lower()
    db = current_app.config["DATABASE"]
    user_id: str = g.user["id"]
    secret_access_code: str = ""  # for anonymous users

    if "anonymous_user" in user_id:
        secret_access_code = db.collection("users").document(user_id).get().to_dict()["secret_access_code"]

    doc_ref = db.collection("studies").document(study_title)
    doc_ref_dict: dict = doc_ref.get().to_dict()

    if user_id in doc_ref_dict["participants"]:
        role: int = doc_ref_dict["participants"].index(user_id)
    elif is_developer():
        role = 1
        user_id = doc_ref_dict["participants"][role]
    else:
        abort(404)

    display_names: dict = db.collection("users").document("display_names").get().to_dict()

    study_type: str = doc_ref_dict["study_type"]
    if "Finished protocol" in doc_ref_dict["status"][user_id]:
        base = "src/static/results"
        shared = f"{study_title}/p{role}"
        os.makedirs(f"{base}/{shared}", exist_ok=True)

        if study_type in {"SF-GWAS", "MPC-GWAS"}:
            if not os.path.exists(f"{base}/{shared}/manhattan.png"):
                download_blob_to_filename(
                    "sfkit",
                    f"{shared}/manhattan.png",
                    f"{base}/{shared}/manhattan.png",
                )
        elif study_type == "PCA":
            if not os.path.exists(f"{base}/{shared}/pca_plot.png"):
                download_blob_to_filename(
                    "sfkit",
                    f"{shared}/pca_plot.png",
                    f"{base}/{shared}/pca_plot.png",
                )

    return make_response(
        render_template(
            "studies/study/study.html",
            study=doc_ref_dict,
            role=role,
            user_id=user_id,
            study_type=study_type,
            parameters=doc_ref_dict["personal_parameters"][user_id],
            display_names=display_names,
            default_tab=request.args.get("default_tab", "main_study"),
            secret_access_code=secret_access_code,
        )
    )


@bp.route("/anonymous/study/<study_title>/<user_id>/<secret_access_code>", methods=("GET", "POST"))
def anonymous_study(study_title: str, user_id: str, secret_access_code: str) -> Response:
    email: str = f"{user_id}@sfkit.org" if "@" not in user_id else user_id
    password: str = secret_access_code
    redirect_url: str = url_for("studies.study", study_title=study_title)
    try:
        return update_user(email, password, redirect_url)
    except Exception as e:
        print(f"Failed in anonymous_study: {e}")
        abort(404)


@bp.route("/study/<study_title>/send_message", methods=["POST"])
@login_required
def send_message(study_title: str) -> Response:
    study_title = study_title.replace(" ", "").lower()
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title)
    doc_ref_dict: dict = doc_ref.get().to_dict()

    message: str = request.form["message"]
    if not message:
        return redirect(url_for("studies.study", study_title=study_title))

    doc_ref_dict["messages"] = doc_ref_dict.get("messages", []) + [
        {
            "sender": g.user["id"],
            "time": datetime.now().strftime("%m/%d/%Y %H:%M"),
            "body": message,
        }
    ]

    doc_ref.set(doc_ref_dict)

    return redirect(url_for("studies.study", study_title=study_title, default_tab="chat_study"))


@bp.route("/choose_study_type", methods=["POST"])
def choose_study_type() -> Response:
    study_type: str = request.form["CHOOSE_STUDY_TYPE"]
    setup_configuration: str = request.form["SETUP_CONFIGURATION"]

    redirect_url: str = url_for("studies.create_study", study_type=study_type, setup_configuration=setup_configuration)
    return redirect(redirect_url) if g.user else create_user(redirect_url=redirect_url)


@bp.route("/create_study/<study_type>/<setup_configuration>", methods=("GET", "POST"))
@login_required
def create_study(study_type: str, setup_configuration: str) -> Response:
    if request.method == "GET":
        return make_response(
            render_template(
                "studies/create_study.html", study_type=study_type, setup_configuration=setup_configuration
            )
        )

    print(f"Creating study of type {study_type} with setup configuration {setup_configuration}")
    title: str = request.form["title"]
    demo: bool = request.form.get("demo_study") == "on"
    user_id: str = g.user["id"]

    (valid, response) = valid_study_title(title, study_type, setup_configuration)
    if not valid:
        return response

    doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
    doc_ref.set(
        {
            "title": title,
            "study_type": study_type,
            "setup_configuration": setup_configuration,
            "private": request.form.get("private_study") == "on" or demo,
            "demo": demo,
            "description": request.form["description"],
            "study_information": request.form["study_information"],
            "owner": user_id,
            "created": datetime.now(),
            "participants": ["Broad", user_id],
            "status": {"Broad": "ready to begin protocol", user_id: ""},
            "parameters": constants.SHARED_PARAMETERS[study_type],
            "advanced_parameters": constants.ADVANCED_PARAMETERS[study_type],
            "personal_parameters": {
                "Broad": constants.broad_user_parameters(),
                user_id: constants.default_user_parameters(study_type, demo),
            },
            "requested_participants": [],
            "invited_participants": [],
        }
    )
    make_auth_key(title, "Broad")

    return response


@bp.route("/restart_study/<study_title>", methods=("POST",))
@login_required
def restart_study(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()

    threads = []
    for role, v in enumerate(doc_ref_dict["participants"]):
        participant = doc_ref_dict["personal_parameters"][v]
        if (gcp_project := participant.get("GCP_PROJECT").get("value")) != "":
            google_cloud_compute = GoogleCloudCompute(study_title.replace(" ", "").lower(), gcp_project)
            for instance in google_cloud_compute.list_instances():
                if instance == create_instance_name(google_cloud_compute.study_title, str(role)):
                    t = Thread(target=google_cloud_compute.delete_instance, args=(instance,))
                    t.start()
                    threads.append(t)
    for t in threads:
        t.join()
    print("Successfully Deleted gcp instances")

    for participant in doc_ref_dict["participants"]:
        doc_ref_dict["status"][participant] = "ready to begin protocol" if participant == "Broad" else ""
        doc_ref_dict["personal_parameters"][participant]["PUBLIC_KEY"]["value"] = ""
    doc_ref_dict["tasks"] = {}

    doc_ref.set(doc_ref_dict)

    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/delete_study/<study_title>", methods=("POST",))
@login_required
def delete_study(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()

    def delete_gcp_stuff_background(doc_ref_dict: dict) -> None:
        # delete gcp stuff
        for participant in doc_ref_dict["personal_parameters"].values():
            if (gcp_project := participant.get("GCP_PROJECT").get("value")) != "":
                google_cloud_compute = GoogleCloudCompute(study_title.replace(" ", "").lower(), gcp_project)
                google_cloud_compute.delete_everything()
        print("Successfully Deleted gcp stuff")

    Thread(target=delete_gcp_stuff_background, args=(doc_ref_dict,)).start()

    # delete auth_keys for study
    for participant in doc_ref_dict["personal_parameters"].values():
        if (auth_key := participant.get("AUTH_KEY").get("value")) != "":
            doc_ref_auth_keys = db.collection("users").document("auth_keys")
            doc_ref_auth_keys.update({auth_key: firestore.DELETE_FIELD})

    # save study to deleted studies collection
    db.collection("deleted_studies").document(
        study_title.replace(" ", "").lower() + "-" + str(doc_ref_dict["created"]).replace(" ", "").lower()
    ).set(doc_ref_dict)

    doc_ref.delete()
    return redirect(url_for("studies.index"))


@bp.route("/request_join_study/<study_title>", methods=["GET", "POST"])
def request_join_study(study_title: str) -> Response:
    if not g.user:
        return create_user(redirect_url=url_for("studies.request_join_study", study_title=study_title))

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()

    message: str = request.form.get("message", "")

    if not doc_ref_dict["requested_participants"]:
        doc_ref_dict["requested_participants"] = {g.user["id"]: message}
    else:
        doc_ref_dict["requested_participants"][g.user["id"]] = message
    doc_ref.set(
        {"requested_participants": doc_ref_dict["requested_participants"]},
        merge=True,
    )
    return redirect(url_for("studies.index"))


@bp.route("/invite_participant/<study_title>", methods=["POST"])
@login_required
def invite_participant(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref_dict = db.collection("users").document("display_names").get().to_dict()

    inviter: str = doc_ref_dict.get(g.user["id"], g.user["id"])
    invitee: str = request.form["invite_participant_email"]
    message: str = request.form.get("invite_participant_message", "")

    if email(inviter, invitee, message, study_title) >= 400:
        return redirect_with_flash(
            url=url_for("studies.study", study_title=study_title), message="Email failed to send"
        )

    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()
    doc_ref_dict["invited_participants"].append(invitee)
    doc_ref.set(
        {"invited_participants": doc_ref_dict["invited_participants"]},
        merge=True,
    )
    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/approve_join_study/<study_title>/<user_id>")
@login_required
def approve_join_study(study_title: str, user_id: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()

    del doc_ref_dict["requested_participants"][user_id]
    doc_ref_dict["participants"] = doc_ref_dict["participants"] + [user_id]
    doc_ref_dict["personal_parameters"] = doc_ref_dict["personal_parameters"] | {
        user_id: constants.default_user_parameters(doc_ref_dict["study_type"])
    }
    doc_ref_dict["status"] = doc_ref_dict["status"] | {user_id: ""}

    doc_ref.set(doc_ref_dict, merge=True)

    add_notification(f"You have been accepted to {study_title}", user_id=user_id)
    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/accept_invitation/<study_title>", methods=["GET", "POST"])
@login_required
def accept_invitation(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()

    if g.user["id"] not in doc_ref_dict["invited_participants"]:
        return redirect_with_flash(
            url=url_for("studies.index"),
            message="The logged in user is not invited to this study.  If you came here from an email invitation, please log in with the email address you were invited with before accepting the invitation.",
        )

    doc_ref_dict["invited_participants"].remove(g.user["id"])

    doc_ref.set(
        {
            "invited_participants": doc_ref_dict["invited_participants"],
            "participants": doc_ref_dict["participants"] + [g.user["id"]],
            "personal_parameters": doc_ref_dict["personal_parameters"]
            | {g.user["id"]: constants.default_user_parameters(doc_ref_dict["study_type"])},
            "status": doc_ref_dict["status"] | {g.user["id"]: ""},
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
        display_names = db.collection("users").document("display_names").get().to_dict()
        return make_response(
            render_template(
                "studies/parameters.html",
                study=doc_ref_dict,
                display_names=display_names,
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
            if p == "NUM_CPUS":
                parameters[g.user["id"]]["NUM_THREADS"]["value"] = request.form.get(p)
    doc_ref.set({"personal_parameters": parameters}, merge=True)
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


@bp.route("/study/<study_title>/download_results_file", methods=("GET",))
@login_required
def download_results_file(study_title: str) -> Response:
    study_title = study_title.replace(" ", "").lower()
    doc_ref_dict = current_app.config["DATABASE"].collection("studies").document(study_title).get().to_dict()
    role: str = str(doc_ref_dict["participants"].index(g.user["id"]))

    base = "src/static/results"
    shared = f"{study_title}/p{role}"
    os.makedirs(f"{base}/{shared}", exist_ok=True)

    result_success = download_blob_to_filename(
        "sfkit",
        f"{shared}/result.txt",
        f"{base}/{shared}/result.txt",
    )

    plot_name = "manhattan" if "GWAS" in doc_ref_dict["study_type"] else "pca_plot"
    plot_success = download_blob_to_filename(
        "sfkit",
        f"{shared}/{plot_name}.png",
        f"{base}/{shared}/{plot_name}.png",
    )

    if not (result_success or plot_success):
        return send_file(
            io.BytesIO("Failed to get results".encode()),
            download_name="result.txt",
            mimetype="text/plain",
            as_attachment=True,
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if result_success:
            add_file_to_zip(zip_file, f"{base}/{shared}/result.txt", "result.txt")
        if plot_success:
            add_file_to_zip(zip_file, f"{base}/{shared}/{plot_name}.png", f"{plot_name}.png")

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        download_name=f"{study_title}_p{role}_results.zip",
        mimetype="application/zip",
        as_attachment=True,
    )


@bp.route("/study/<study_title>/start_protocol", methods=["POST"])
@login_required
def start_protocol(study_title: str) -> Response:
    user_id: str = g.user["id"]
    doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()
    num_inds: str = doc_ref_dict["personal_parameters"][user_id]["NUM_INDS"]["value"]
    gcp_project: str = doc_ref_dict["personal_parameters"][user_id]["GCP_PROJECT"]["value"]
    data_path: str = doc_ref_dict["personal_parameters"][user_id]["DATA_PATH"]["value"]
    statuses: dict = doc_ref_dict["status"]
    demo: bool = doc_ref_dict["demo"]

    if statuses[user_id] == "":
        if not demo and not num_inds:
            return redirect_with_flash(
                url=url_for("studies.study", study_title=study_title),
                message="Your have not set the number of individuals/rows in your data.  Please click on the 'Study Parameters' button to set this value and any other parameters you wish to change before running the protocol.",
            )
        if not gcp_project:
            return redirect_with_flash(
                url=url_for("studies.study", study_title=study_title),
                message="Your GCP project ID is not set.  Please follow the instructions in the 'Configure Study' button before running the protocol.",
            )
        if not demo and "broad-cho-priv1" in gcp_project and os.environ.get("FLASK_DEBUG") != "development":
            return redirect_with_flash(
                url=url_for("studies.study", study_title=study_title),
                message="This project ID is only allowed for a demo study.  Please follow the instructions in the 'Configure Study' button to set up your own GCP project before running the protocol.",
            )
        if not demo and not data_path:
            return redirect_with_flash(
                url=url_for("studies.study", study_title=study_title),
                message="Your data path is not set.  Please follow the instructions in the 'Configure Study' button before running the protocol.",
            )
        if not GoogleCloudIAM().test_permissions(gcp_project):
            return redirect_with_flash(
                url=url_for("studies.study", study_title=study_title),
                message="You have not given the website the necessary GCP permissions for the project you have entered.  Please click on 'Configure Study' to double-check that your project ID is correct and that you have given the website the necessary permissions (and they are not expired) in that GCP project.",
            )

        doc_ref_dict = doc_ref.get().to_dict()
        statuses = doc_ref_dict["status"]
        statuses[user_id] = "ready to begin sfkit"
        doc_ref.set({"status": statuses}, merge=True)

    if "" in statuses.values():
        print("Not all participants are ready.")
    elif statuses[user_id] == "ready to begin sfkit":
        for role in range(1, len(doc_ref_dict["participants"])):
            user = doc_ref_dict["participants"][role]
            doc_ref_dict = doc_ref.get().to_dict()
            statuses = doc_ref_dict["status"]
            statuses[user] = "setting up your vm instance"
            doc_ref.set({"status": statuses}, merge=True)

            make_auth_key(study_title, user)

            Thread(target=setup_gcp, args=(doc_ref, str(role))).start()

            time.sleep(1)

    return redirect(url_for("studies.study", study_title=study_title))
