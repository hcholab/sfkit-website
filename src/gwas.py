from datetime import datetime
import re

from flask import (
    Blueprint,
    current_app,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from src import constants
from src.auth import login_required
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM
from src.utils.google_cloud.google_cloud_pubsub import GoogleCloudPubsub
from src.utils.google_cloud.google_cloud_storage import GoogleCloudStorage
from src.utils.helper_functions import flash

bp = Blueprint("gwas", __name__)


@bp.route("/index")
def index():
    db = current_app.config["DATABASE"]
    projects = db.collection("projects")
    projects = [project.to_dict() for project in projects.stream()]

    return render_template("gwas/index.html", projects=projects)


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        db = current_app.config["DATABASE"]

        title = request.form["title"]
        description = request.form["description"]

        if not re.match(r"^[a-zA-Z][ a-zA-Z0-9-]*$", title):
            r = redirect(url_for("gwas.create"))
            message = "Title can include only letters, numbers, spaces, and dashes, and must start with a letter."
            flash(r, message)
            return r

        # validate that title is unique
        projects = db.collection("projects").stream()
        for project in projects:
            if (
                project.to_dict()["title"].replace(" ", "").lower()
                == title.replace(" ", "").lower()
            ):
                r = redirect(url_for("gwas.create"))
                flash(r, "Title already exists.")
                return r

        doc_ref = db.collection("projects").document(title.replace(" ", "").lower())
        doc_ref.set(
            {
                "title": title,
                "description": description,
                "owner": g.user["id"],
                "created": datetime.now(),
                "participants": [g.user["id"]],
                "status": {"0": ["not ready"]},
                "parameters": constants.DEFAULT_PARAMETERS,
                "personal_parameters": {
                    g.user["id"]: constants.DEFAULT_PERSONAL_PARAMETERS
                },
                "requested_participants": [],
            }
        )
        return redirect(url_for("gwas.index"))
    return render_template("gwas/create.html")


@bp.route("/update/<project_title>", methods=("GET", "POST"))
@login_required
def update(project_title):
    db = current_app.config["DATABASE"]

    project = (
        db.collection("projects")
        .document(project_title.replace(" ", "").lower())
        .get()
        .to_dict()
    )

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]

        if title.replace(" ", "").lower() != project_title.replace(" ", "").lower():
            # validate that title is unique
            projects = db.collection("projects").stream()
            for project in projects:
                if (
                    project.to_dict()["title"].replace(" ", "").lower()
                    == title.replace(" ", "").lower()
                ):
                    r = redirect(url_for("gwas.update", project_title=project))
                    flash(r, "Title already exists.")
                    return r

        old_doc_ref = db.collection("projects").document(
            project_title.replace(" ", "").lower()
        )
        old_doc_ref_dict = old_doc_ref.get().to_dict()
        doc_ref = db.collection("projects").document(title.replace(" ", "").lower())
        doc_ref.set(
            {
                "title": title,
                "description": description,
                "owner": g.user["id"],
                "created": old_doc_ref_dict["created"],
                "participants": old_doc_ref_dict["participants"],
                "status": {"0": ["not ready"]},
                "parameters": old_doc_ref_dict["parameters"],
                "personal_parameters": old_doc_ref_dict["personal_parameters"],
                "requested_participants": [],
            },
            merge=True,
        )
        if (
            project_title != title
        ):  # in this case, we're creating a new post, so we delete the old one
            old_doc_ref.delete()
        return redirect(url_for("gwas.index"))

    return render_template("gwas/update.html", project=project)


@bp.route("/delete/<project_title>", methods=("POST",))
@login_required
def delete(project_title):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("projects").document(project_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()

    google_cloud_compute = GoogleCloudCompute("")
    for participant in doc_ref_dict["personal_parameters"].values():
        print(participant)
        if (gcp_project := participant.get("GCP_PROJECT").get("value")) != "":
            print(gcp_project)
            google_cloud_compute.project = gcp_project
            for instance in google_cloud_compute.list_instances():
                if constants.INSTANCE_NAME_ROOT in instance:
                    google_cloud_compute.delete_instance(instance)

    doc_ref.delete()
    return redirect(url_for("gwas.index"))


@bp.route("/join/<project_name>", methods=("GET", "POST"))
@login_required
def request_join_project(project_name):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("projects").document(project_name.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref.set(
        {
            "requested_participants": doc_ref_dict["requested_participants"]
            + [g.user["id"]]
        },
        merge=True,
    )

    return redirect(url_for("gwas.index"))


@bp.route("/approve_join_project/<project_name>/<user_id>", methods=("GET", "POST"))
def approve_join_project(project_name, user_id):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("projects").document(project_name.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref.set(
        {
            "participants": doc_ref_dict["participants"] + [user_id],
            "requested_participants": doc_ref_dict["requested_participants"].remove(
                user_id
            ),
            "personal_parameters": doc_ref_dict["personal_parameters"]
            | {user_id: constants.DEFAULT_PERSONAL_PARAMETERS},
        },
        merge=True,
    )
    return redirect(url_for("gwas.start", project_title=project_name))


@bp.route("/start/<project_title>", methods=("GET", "POST"))
@login_required
def start(project_title):
    db = current_app.config["DATABASE"]
    project_doc_dict = (
        db.collection("projects")
        .document(project_title.replace(" ", "").lower())
        .get()
        .to_dict()
    )
    public_keys = [
        project_doc_dict["personal_parameters"][user]["PUBLIC_KEY"]["value"]
        for user in project_doc_dict["participants"]
    ]
    id = g.user["id"]
    role: int = project_doc_dict["participants"].index(id)

    if request.method == "GET":
        return render_template(
            "gwas/start.html",
            project=project_doc_dict,
            public_keys=public_keys,
            role=role,
        )
    gcp_project = project_doc_dict["personal_parameters"][id]["GCP_PROJECT"]["value"]
    if gcp_project == "" or gcp_project is None:
        r = redirect(url_for("gwas.personal_parameters", project_title=project_title))
        flash(r, "Please set your GCP project.")
        r.set_cookie("flash", "Please set your GCP project first.")
        return r

    # check if pos.txt is in the google cloud bucket
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    if not gcloudStorage.check_file_exists("pos.txt"):
        message = "Please upload a pos.txt file or have one of the entities you are runnning this project with do so for you."
        r = redirect(
            url_for("gwas.parameters", project_title=project_title, section="pos")
        )
        flash(r, message)
        return r

    statuses = project_doc_dict["status"]
    if statuses[str(role)] == ["not ready"]:
        gcloudIAM = GoogleCloudIAM()
        if gcloudIAM.test_permissions(gcp_project):
            statuses[str(role)] = ["ready"]
            db.collection("projects").document(
                project_title.replace(" ", "").lower()
            ).set(
                {"status": statuses},
                merge=True,
            )
        else:
            r = redirect(url_for("general.permissions"))
            flash(r, "Please give the service appropriate permissions first.")
            return r

    if any("not ready" in status for status in statuses.values()):
        pass
    elif statuses[str(role)] == ["ready"]:
        statuses[str(role)] = ["setting up your vm instance"]
        db.collection("projects").document(project_title.replace(" ", "").lower()).set(
            {"status": statuses},
            merge=True,
        )
        run_gwas(
            str(role),
            gcp_project,
            project_title,
            size=project_doc_dict["personal_parameters"][id]["VM_SIZE"]["value"],
        )
    else:
        statuses[role] = get_status(
            str(role), gcp_project, statuses[role], project_title
        )
        db.collection("projects").document(project_title.replace(" ", "").lower()).set(
            {"status": statuses},
            merge=True,
        )

    project_doc_dict = (
        db.collection("projects")
        .document(project_title.replace(" ", "").lower())
        .get()
        .to_dict()
    )
    return render_template(
        "gwas/start.html", project=project_doc_dict, public_keys=public_keys, role=role
    )


@bp.route("/parameters/<project_title>", methods=("GET", "POST"))
@login_required
def parameters(project_title):
    google_cloud_storage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("projects").document(project_title.replace(" ", "").lower())
    parameters = doc_ref.get().to_dict().get("parameters")
    pos_file_uploaded = google_cloud_storage.check_file_exists("pos.txt")
    if request.method == "GET":
        return render_template(
            "gwas/parameters.html",
            project_title=project_title,
            parameters=parameters,
            pos_file_uploaded=pos_file_uploaded,
        )
    elif "save" in request.form:
        for p in parameters["index"]:
            parameters[p]["value"] = request.form.get(p)
        doc_ref.set({"parameters": parameters}, merge=True)
        return redirect(url_for("gwas.start", project_title=project_title))
    elif "upload" in request.form:
        file = request.files["file"]
        if file.filename == "":
            r = redirect(url_for("gwas.parameters", project_title=project_title))
            flash(r, "Please select a file to upload.")
            return r
        elif file and file.filename == "pos.txt":
            gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
            gcloudStorage.upload_to_bucket(file, file.filename)
            return redirect(url_for("gwas.start", project_title=project_title))
        else:
            r = redirect(url_for("gwas.parameters", project_title=project_title))
            flash(r, "Please upload a valid pos.txt file.")
            return r
    else:
        print("Unknown request")
        exit(1)


@bp.route("/personal_parameters/<project_title>", methods=("GET", "POST"))
def personal_parameters(project_title):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("projects").document(project_title.replace(" ", "").lower())
    parameters = doc_ref.get().to_dict().get("personal_parameters")

    if request.method == "GET":
        return render_template(
            "gwas/personal_parameters.html",
            project_title=project_title,
            parameters=parameters[g.user["id"]],
        )

    for p in parameters[g.user["id"]]["index"]:
        parameters[g.user["id"]][p]["value"] = request.form.get(p)
    doc_ref.set({"personal_parameters": parameters}, merge=True)
    return redirect(url_for("gwas.start", project_title=project_title))


def get_status(role: str, gcp_project, status, project_title):
    if status == "GWAS Completed!":
        return status

    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, project_title)
    gcloudCompute = GoogleCloudCompute(gcp_project)
    status = gcloudPubsub.listen_to_startup_script(status)

    if status == "GWAS Completed!":
        instance = (
            project_title.replace(" ", "").lower()
            + "-"
            + constants.INSTANCE_NAME_ROOT
            + role
        )
        gcloudCompute.stop_instance(constants.ZONE, instance)
        gcloudPubsub.delete_topic()
    return status


def run_gwas(role, gcp_project, project_title, size):
    gcloudCompute = GoogleCloudCompute(gcp_project)
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, project_title)

    # copy parameters to parameter files
    gcloudStorage.copy_parameters_to_bucket(project_title, role)

    gcloudPubsub.create_topic_and_subscribe()
    instance = (
        project_title.replace(" ", "").lower()
        + "-"
        + constants.INSTANCE_NAME_ROOT
        + role
    )
    gcloudCompute.setup_networking(role)
    gcloudCompute.setup_instance(constants.ZONE, instance, role, size)

    # Give instance publish access to pubsub for status updates
    member = "serviceAccount:" + gcloudCompute.get_service_account_for_vm(
        zone=constants.ZONE, instance=instance
    )
    gcloudPubsub.add_pub_iam_member("roles/pubsub.publisher", member)
    # give instance read access to storage buckets for parameter files
    gcloudStorage.add_bucket_iam_member(
        constants.BUCKET_NAME, "roles/storage.objectViewer", member
    )

    # # Create bucket to store the ip addresses; this will be read-only for the VMs
    # bucket = gcloudStorage.validate_bucket(role)
    # blob = bucket.blob("ip_addresses/P" + role)
    # blob.upload_from_string(vm_external_ip_address)

    # # Give the instance's service account read-access to this bucket
    # gcloudStorage.add_bucket_iam_member(
    #     constants.BUCKET_NAME, "roles/storage.objectViewer", member)

    print("I've done what I can.  GWAS should be running now.")
