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


@bp.route("/start/<project_title>/<role>", methods=("GET", "POST"))
@login_required
def start(project_title, role):
    db = current_app.config["DATABASE"]
    project_doc_dict = db.collection("projects").document(project_title).get().to_dict()
    id = g.user["id"]
    role = str(project_doc_dict["participants"].index(id))

    if request.method == "GET":
        return render_template(
            "gwas/start.html", project=project_doc_dict, role=int(role)
        )
    gcp_project = db.collection("users").document(id).get().to_dict().get("gcp_project")
    if not gcp_project:
        flash("Please set your GCP project first.")
        return redirect(url_for("auth.user", id=id))
    statuses = project_doc_dict["status"]

    if statuses[int(role)] == "not ready":
        gcloudIAM = GoogleCloudIAM()
        if gcloudIAM.test_permissions(gcp_project):
            statuses[int(role)] = "ready"
            db.collection("projects").document(project_title).set(
                {"status": statuses},
                merge=True,
            )
        else:
            flash("Please give the service appropriate permissions first.")
            return redirect(url_for("general.permissions"))
    if "not ready" in statuses:
        pass
    elif statuses[int(role)] == "ready":
        statuses[int(role)] = "setting up your vm instance"
        db.collection("projects").document(project_title).set(
            {"status": statuses},
            merge=True,
        )

        run_gwas(role, gcp_project, project_title)
    else:
        statuses[int(role)] = get_status(
            role, gcp_project, statuses[int(role)], project_title
        )
        db.collection("projects").document(project_title).set(
            {"status": statuses},
            merge=True,
        )

    project_doc_dict = db.collection("projects").document(project_title).get().to_dict()
    return render_template("gwas/start.html", project=project_doc_dict, role=int(role))


def get_status(role, gcp_project, status, project_title):
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, project_title)
    gcloudCompute = GoogleCloudCompute(gcp_project)
    status = gcloudPubsub.listen_to_startup_script(status)

    if status == "GWAS Completed!" or (
        status == "DataSharing Completed!" and role == "3"
    ):
        instance = (
            project_title.replace(" ", "").lower()
            + "-"
            + constants.INSTANCE_NAME_ROOT
            + role
        )
        gcloudCompute.stop_instance(constants.ZONE, instance)
    return status


def run_gwas(role, gcp_project, project_title):
    gcloudCompute = GoogleCloudCompute(gcp_project)
    # gcloudStorage = GoogleCloudStorage(constants.SERVER_PROJECT)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, project_title)

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

    # # Create bucket to store the ip addresses; this will be read-only for the VMs
    # bucket = gcloudStorage.validate_bucket(role)
    # blob = bucket.blob("ip_addresses/P" + role)
    # blob.upload_from_string(vm_external_ip_address)

    # # Give the instance's service account read-access to this bucket
    # gcloudStorage.add_bucket_iam_member(
    #     constants.BUCKET_NAME, "roles/storage.objectViewer", member)

    print("I've done what I can.  GWAS should be running now.")
