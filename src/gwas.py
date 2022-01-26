from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
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

        if not title:
            flash("Title is required.")
        else:
            # validate that title is unique
            projects = db.collection("projects").stream()
            for project in projects:
                if (
                    project.to_dict()["title"].replace(" ", "").lower()
                    == title.replace(" ", "").lower()
                ):
                    flash("Title already exists.")
                    return render_template("gwas/create.html")

            doc_ref = db.collection("projects").document(title)
            doc_ref.set(
                {
                    "title": title,
                    "description": description,
                    "owner": g.user["id"],
                    "created": datetime.now(),
                    "participants": [g.user["id"]],
                    "status": ["not ready"],
                    "parameters": constants.DEFAULT_PARAMETERS,
                }
            )
            return redirect(url_for("gwas.index"))
    return render_template("gwas/create.html")


@bp.route("/update/<project_title>", methods=("GET", "POST"))
@login_required
def update(project_title):
    db = current_app.config["DATABASE"]

    project = db.collection("projects").document(project_title).get().to_dict()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]

        if not title:
            flash("Title is required.")
        else:
            if title.replace(" ", "").lower() != project_title.replace(" ", "").lower():
                # validate that title is unique
                projects = db.collection("projects").stream()
                for project in projects:
                    if (
                        project.to_dict()["title"].replace(" ", "").lower()
                        == title.replace(" ", "").lower()
                    ):
                        flash("Title already exists.")
                        return render_template("gwas/update.html", project=project)

            old_doc_ref = db.collection("projects").document(project_title)
            old_doc_ref_dict = old_doc_ref.get().to_dict()
            doc_ref = db.collection("projects").document(title)
            doc_ref.set(
                {
                    "title": title,
                    "description": description,
                    "owner": g.user["id"],
                    "created": old_doc_ref_dict["created"],
                    "participants": old_doc_ref_dict["participants"],
                    "status": ["not ready"],
                    "parameters": old_doc_ref_dict["parameters"],
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
    db.collection("projects").document(project_title).delete()
    return redirect(url_for("gwas.index"))


@bp.route("/join/<project_name>", methods=("POST",))
@login_required
def join_project(project_name):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("projects").document(project_name)
    doc_ref.set(
        {
            "participants": doc_ref.get().to_dict()["participants"] + [g.user["id"]],
            "status": doc_ref.get().to_dict()["status"] + ["not ready"],
        },
        merge=True,
    )
    return redirect(url_for("gwas.index"))


@bp.route("/start/<project_title>", methods=("GET", "POST"))
@login_required
def start(project_title):
    db = current_app.config["DATABASE"]
    project_doc_dict = db.collection("projects").document(project_title).get().to_dict()
    public_keys = [
        db.collection("users").document(user).get().to_dict()["public_key"]
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
    gcp_project = db.collection("users").document(id).get().to_dict().get("gcp_project")
    if not gcp_project:
        flash("Please set your GCP project first.")
        return redirect(url_for("auth.user", id=id))

    # check if pos.txt is in the google cloud bucket
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    if not gcloudStorage.check_file_exists("pos.txt"):
        flash("A pos.txt file is required to begin the workflow.")
        flash(
            "Please either upload a pos.txt file yourself or have one of the entities you are running this project with do so for you."
        )
        return redirect(
            url_for("gwas.parameters", project_title=project_title, section="pos")
        )

    statuses = project_doc_dict["status"]
    if statuses[role] == "not ready":
        gcloudIAM = GoogleCloudIAM()
        if gcloudIAM.test_permissions(gcp_project):
            statuses[role] = "ready"
            db.collection("projects").document(project_title).set(
                {"status": statuses},
                merge=True,
            )
        else:
            flash("Please give the service appropriate permissions first.")
            return redirect(url_for("general.permissions"))

    if "not ready" in statuses:
        pass
    elif statuses[role] == "ready":
        statuses[role] = "setting up your vm instance"
        db.collection("projects").document(project_title).set(
            {"status": statuses},
            merge=True,
        )
        run_gwas(str(role), gcp_project, project_title)
    else:
        statuses[role] = get_status(
            str(role), gcp_project, statuses[role], project_title
        )
        db.collection("projects").document(project_title).set(
            {"status": statuses},
            merge=True,
        )

    project_doc_dict = db.collection("projects").document(project_title).get().to_dict()
    return render_template(
        "gwas/start.html", project=project_doc_dict, public_keys=public_keys, role=role
    )


@bp.route("/parameters/<project_title>", methods=("GET", "POST"))
@login_required
def parameters(project_title):
    google_cloud_storage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("projects").document(project_title)
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
            flash("Please select a file to upload.")
            return redirect(url_for("gwas.parameters", project_title=project_title))
        elif file and file.filename == "pos.txt":
            gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
            gcloudStorage.upload_to_bucket(file, file.filename)
            return redirect(url_for("gwas.start", project_title=project_title))
        else:
            flash("Please upload a valid pos.txt file.")
            return redirect(url_for("gwas.parameters", project_title=project_title))
    else:
        print("Unknown request")
        exit(1)


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


def run_gwas(role, gcp_project, project_title):
    gcloudCompute = GoogleCloudCompute(gcp_project)
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, project_title)

    # copy parameters to parameter files
    gcloudStorage.copy_parameters_to_bucket(project_title)

    gcloudPubsub.create_topic_and_subscribe()
    instance = (
        project_title.replace(" ", "").lower()
        + "-"
        + constants.INSTANCE_NAME_ROOT
        + role
    )
    gcloudCompute.setup_networking(role)
    gcloudCompute.setup_instance(constants.ZONE, instance, role)

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
