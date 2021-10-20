from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from google.api_core.gapic_v1 import method
from google.cloud import firestore
from google.protobuf import descriptor

from src import constants
from src.auth import login_required
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from src.utils.google_cloud.google_cloud_pubsub import GoogleCloudPubsub

bp = Blueprint("gwas", __name__)
db = firestore.Client()


@bp.route("/index")
def index():
    projects = db.collection("projects")
    projects = [project.to_dict() for project in projects.stream()]

    return render_template("gwas/index.html", projects=projects)


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]

        if not title:
            flash("Title is required.")
        else:
            doc_ref = db.collection("projects").document(title)
            doc_ref.set(
                {
                    "title": title,
                    "description": description,
                    "owner": g.user["id"],
                    "created": datetime.now(),
                    "participants": [g.user["id"]],
                    "ready": [0],
                    "status": "not ready",
                }
            )
            return redirect(url_for("gwas.index"))
    return render_template("gwas/create.html")


@bp.route("/<string:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    project = db.collection("projects").document(id).get().to_dict()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]

        if not title:
            flash("Title is required.")
        else:
            old_doc_ref = db.collection("projects").document(id)
            old_doc_ref_dict = old_doc_ref.get().to_dict()
            doc_ref = db.collection("projects").document(title)
            doc_ref.set(
                {
                    "title": title,
                    "description": description,
                    "owner": g.user["id"],
                    "created": old_doc_ref_dict["created"],
                    "participants": old_doc_ref_dict["participants"],
                    "ready": old_doc_ref_dict["ready"],
                    "status": "not ready",
                },
                merge=True,
            )
            if (
                id != title
            ):  # in this case, we're creating a new post, so we delete the old one
                old_doc_ref.delete()
            return redirect(url_for("gwas.index"))

    return render_template("gwas/update.html", project=project)


@bp.route("/delete/<id>", methods=("POST",))
@login_required
def delete(id):
    db.collection("projects").document(id).delete()
    return redirect(url_for("gwas.index"))


@bp.route("/<string:id>/join", methods=("POST",))
@login_required
def join_project(id):
    doc_ref = db.collection("projects").document(id)
    doc_ref.set(
        {
            "participants": doc_ref.get().to_dict()["participants"] + [g.user["id"]],
            "ready": doc_ref.get().to_dict()["ready"] + [0],
        },
        merge=True,
    )
    return redirect(url_for("gwas.index"))


@bp.route("/start/<project_title>", methods=("GET", "POST"))
@login_required
def start(project_title):
    project_doc_dict = db.collection("projects").document(project_title).get().to_dict()

    if request.method == "GET":
        return render_template("gwas/start.html", project=project_doc_dict)
    elif request.method == "POST":
        id = g.user["id"]
        role = str(project_doc_dict["participants"].index(id))
        gcp_project = db.collection("users").document(id).get().to_dict()["gcp_project"]

        status = project_doc_dict["status"]
        if status == "not ready":
            updated_ready = project_doc_dict["ready"]
            updated_ready[int(role)] = 1
            db.collection("projects").document(project_title).set(
                {"status": "waiting for others", "ready": updated_ready}, merge=True
            )
        elif 0 in project_doc_dict["ready"]:
            pass
        elif status == "waiting for others":
            db.collection("projects").document(project_title).set(
                {"status": "setting up the vm instances"}, merge=True
            )

            run_gwas(role, gcp_project)
        else:
            db.collection("projects").document(project_title).set(
                {"status": get_status(role, gcp_project, status)}, merge=True
            )

        project_doc_dict = (
            db.collection("projects").document(project_title).get().to_dict()
        )
        return render_template("gwas/start.html", project=project_doc_dict)


def get_status(role, gcp_project, status):
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role)
    gcloudCompute = GoogleCloudCompute(gcp_project)
    status = gcloudPubsub.listen_to_startup_script(status)

    if status == "GWAS Completed!" or (
        status == "DataSharing Completed!" and role == "3"
    ):
        gcloudCompute.stop_instance(constants.ZONE, constants.INSTANCE_NAME_ROOT + role)
    return status


def run_gwas(role, gcp_project):
    gcloudCompute = GoogleCloudCompute(gcp_project)
    # gcloudStorage = GoogleCloudStorage(constants.SERVER_PROJECT)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role)

    gcloudPubsub.create_topic_and_subscribe()

    instance = constants.INSTANCE_NAME_ROOT + role

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
