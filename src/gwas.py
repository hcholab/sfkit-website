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
from src.utils.helper_functions import create_instance_name, flash

bp = Blueprint("gwas", __name__)


@bp.route("/index", methods=["GET", "POST"])
def index():
    db = current_app.config["DATABASE"]
    studies = db.collection("studies")
    studies_list = [study.to_dict() for study in studies.stream()]

    if request.method == "GET":
        return render_template("gwas/index.html", studies=studies_list)

    # user wants to join a study
    doc_ref = studies.document(request.form["study_title"].replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["requested_participants"] = [g.user["id"]]
    doc_ref.set(
        {"requested_participants": doc_ref_dict["requested_participants"]},
        merge=True,
    )
    return redirect(url_for("gwas.index"))


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "GET":
        return render_template("gwas/create.html")

    db = current_app.config["DATABASE"]
    title = request.form["title"]
    description = request.form["description"]

    if not re.match(r"^[a-zA-Z][ a-zA-Z0-9-]*$", title):
        r = redirect(url_for("gwas.create"))
        message = "Title can include only letters, numbers, spaces, and dashes, and must start with a letter."
        flash(r, message)
        return r

    # validate that title is unique
    studies = db.collection("studies").stream()
    for study in studies:
        if (
            study.to_dict()["title"].replace(" ", "").lower()
            == title.replace(" ", "").lower()
        ):
            r = redirect(url_for("gwas.create"))
            flash(r, "Title already exists.")
            return r

    doc_ref = db.collection("studies").document(title.replace(" ", "").lower())
    doc_ref.set(
        {
            "title": title,
            "description": description,
            "owner": g.user["id"],
            "created": datetime.now(),
            "participants": [g.user["id"]],
            "status": {g.user["id"]: [""]},
            "parameters": constants.DEFAULT_SHARED_PARAMETERS,
            "personal_parameters": {g.user["id"]: constants.DEFAULT_USER_PARAMETERS},
            "requested_participants": [],
        }
    )
    return redirect(url_for("gwas.index"))


# @bp.route("/update/<project_title>", methods=("GET", "POST"))
# @login_required
# def update(project_title):
#     db = current_app.config["DATABASE"]

#     project = (
#         db.collection("projects")
#         .document(project_title.replace(" ", "").lower())
#         .get()
#         .to_dict()
#     )

#     if request.method == "POST":
#         title = request.form["title"]
#         description = request.form["description"]

#         if title.replace(" ", "").lower() != project_title.replace(" ", "").lower():
#             # validate that title is unique
#             projects = db.collection("projects").stream()
#             for project in projects:
#                 if (
#                     project.to_dict()["title"].replace(" ", "").lower()
#                     == title.replace(" ", "").lower()
#                 ):
#                     r = redirect(url_for("gwas.update", project_title=project))
#                     flash(r, "Title already exists.")
#                     return r

#         old_doc_ref = db.collection("projects").document(
#             project_title.replace(" ", "").lower()
#         )
#         old_doc_ref_dict = old_doc_ref.get().to_dict()
#         doc_ref = db.collection("projects").document(title.replace(" ", "").lower())
#         doc_ref.set(
#             {
#                 "title": title,
#                 "description": description,
#                 "owner": g.user["id"],
#                 "created": old_doc_ref_dict["created"],
#                 "participants": old_doc_ref_dict["participants"],
#                 "status": {"0": [""]},
#                 "parameters": old_doc_ref_dict["parameters"],
#                 "personal_parameters": old_doc_ref_dict["personal_parameters"],
#                 "requested_participants": old_doc_ref_dict["requested_participants"],
#             },
#             merge=True,
#         )
#         if (
#             project_title != title
#         ):  # in this case, we're creating a new post, so we delete the old one
#             old_doc_ref.delete()
#         return redirect(url_for("gwas.index"))

#     return render_template("gwas/update.html", project=project)


@bp.route("/delete/<study_title>", methods=("POST",))
@login_required
def delete(study_title):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()

    # delete vms that may still exist
    google_cloud_compute = GoogleCloudCompute("")
    for participant in doc_ref_dict["personal_parameters"].values():
        if (gcp_project := participant.get("GCP_PROJECT").get("value")) != "":
            google_cloud_compute.project = gcp_project
            for instance in google_cloud_compute.list_instances():
                if constants.INSTANCE_NAME_ROOT in instance:
                    google_cloud_compute.delete_instance(instance)

    doc_ref.delete()
    return redirect(url_for("gwas.index"))


# @bp.route("/join/<project_name>", methods=("GET", "POST"))
# @login_required
# def request_join_project(project_name):
#     db = current_app.config["DATABASE"]
#     doc_ref = db.collection("projects").document(project_name.replace(" ", "").lower())
#     doc_ref_dict = doc_ref.get().to_dict()
#     doc_ref.set(
#         {
#             "requested_participants": doc_ref_dict["requested_participants"]
#             + [g.user["id"]]
#         },
#         merge=True,
#     )

#     return redirect(url_for("gwas.index"))


@bp.route("/approve_join_study/<study_title>/<user_id>", methods=("GET", "POST"))
def approve_join_study(study_title, user_id):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()

    doc_ref.set(
        {
            "requested_participants": doc_ref_dict["requested_participants"].remove(
                user_id
            ),
            "participants": doc_ref_dict["participants"] + [user_id],
            "personal_parameters": doc_ref_dict["personal_parameters"]
            | {user_id: constants.DEFAULT_USER_PARAMETERS},
            "status": doc_ref_dict["status"] | {user_id: [""]},
        },
        merge=True,
    )

    return redirect(url_for("gwas.start", study_title=study_title))


@bp.route("/validate_bucket/<study_title>", methods=("GET", "POST"))
@login_required
def validate_bucket(study_title):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    role: str = str(doc_ref_dict["participants"].index(g.user["id"]) + 1)
    gcp_project = doc_ref_dict["personal_parameters"][g.user["id"]]["GCP_PROJECT"][
        "value"
    ]
    bucket_name = doc_ref_dict["personal_parameters"][g.user["id"]]["BUCKET_NAME"][
        "value"
    ]
    if not gcp_project or gcp_project == "" or not bucket_name or bucket_name == "":
        r = redirect(url_for("gwas.personal_parameters", study_title=study_title))
        flash(r, "Please set your GCP project and storage bucket location.")
        return r

    statuses = doc_ref_dict["status"]
    statuses[g.user["id"]] = ["validating"]
    doc_ref.set({"status": statuses}, merge=True)

    gcloudCompute = GoogleCloudCompute(gcp_project)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, study_title)

    gcloudPubsub.create_topic_and_subscribe()
    instance = create_instance_name(study_title, role)
    gcloudCompute.setup_networking(role)
    gcloudCompute.setup_instance(
        constants.ZONE,
        instance,
        role,
        validate=True,
        metadata={"key": "bucketname", "value": bucket_name},
    )

    # Give instance publish access to pubsub for status updates
    member = "serviceAccount:" + gcloudCompute.get_service_account_for_vm(
        zone=constants.ZONE, instance=instance
    )
    gcloudPubsub.add_pub_iam_member("roles/pubsub.publisher", member)

    return redirect(url_for("gwas.start", study_title=study_title))


@bp.route("/start/<study_title>", methods=("GET", "POST"))
@login_required
def start(study_title):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    public_keys = [
        doc_ref_dict["personal_parameters"][user]["PUBLIC_KEY"]["value"]
        for user in doc_ref_dict["participants"]
    ]
    id = g.user["id"]
    role: int = doc_ref_dict["participants"].index(id) + 1

    if request.method == "GET":
        return render_template(
            "gwas/start.html",
            study=doc_ref_dict,
            public_keys=public_keys,
            role=role,
            parameters=doc_ref_dict["personal_parameters"][id],
        )

    gcp_project = doc_ref_dict["personal_parameters"][id]["GCP_PROJECT"]["value"]

    # check if pos.txt is in the google cloud bucket
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    if not gcloudStorage.check_file_exists("pos.txt"):
        message = "Please upload a pos.txt file or have one of the entities you are runnning this study with do so for you."
        r = redirect(url_for("gwas.parameters", study_title=study_title, section="pos"))
        flash(r, message)
        return r

    statuses = doc_ref_dict["status"]
    if statuses[id] == ["not ready"]:
        gcloudIAM = GoogleCloudIAM()
        if gcloudIAM.test_permissions(gcp_project):
            statuses[id] = ["ready"]
            personal_parameters = doc_ref_dict["personal_parameters"]
            personal_parameters[id]["NUM_CPUS"]["value"] = request.form["NUM_CPUS"]
            personal_parameters[id]["NUM_THREADS"]["value"] = request.form["NUM_CPUS"]
            personal_parameters[id]["BOOT_DISK_SIZE"]["value"] = request.form[
                "BOOT_DISK_SIZE"
            ]
            doc_ref.set(
                {
                    "status": statuses,
                    "personal_parameters": personal_parameters,
                },
                merge=True,
            )

        else:
            r = redirect(url_for("general.permissions"))
            flash(r, "Please give the service appropriate permissions first.")
            return r

    if any("not ready" in status for status in statuses.values()):
        pass
    elif statuses[id] == ["ready"]:
        statuses[id] = ["setting up your vm instance"]

        doc_ref.set(
            {
                "status": statuses,
            },
            merge=True,
        )
        doc_ref_dict = doc_ref.get().to_dict()
        if role == 1:
            # start CP0 as well
            gcloudCompute = GoogleCloudCompute(constants.SERVER_GCP_PROJECT)
            instance = create_instance_name(study_title, "0")
            vm_parameters = doc_ref_dict["personal_parameters"][id]
            gcloudCompute.setup_networking("0")
            gcloudCompute.setup_instance(
                constants.ZONE,
                instance,
                "0",
                vm_parameters["NUM_CPUS"]["value"],
                metadata={
                    "key": "bucketname",
                    "value": vm_parameters["BUCKET_NAME"]["value"],
                },
                boot_disk_size=vm_parameters["BOOT_DISK_SIZE"]["value"],
            )
        run_gwas(
            str(role),
            gcp_project,
            study_title,
            vm_parameters=doc_ref_dict["personal_parameters"][id],
        )
    # else:
    #     statuses[role] = get_status(
    #         str(role), gcp_project, statuses[role], project_title
    #     )
    #     db.collection("projects").document(project_title.replace(" ", "").lower()).set(
    #         {"status": statuses},
    #         merge=True,
    #     )

    doc_ref_dict = (
        db.collection("studies")
        .document(study_title.replace(" ", "").lower())
        .get()
        .to_dict()
    )
    return render_template(
        "gwas/start.html", study=doc_ref_dict, public_keys=public_keys, role=role
    )


@bp.route("/parameters/<study_title>", methods=("GET", "POST"))
@login_required
def parameters(study_title):
    google_cloud_storage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    parameters = doc_ref.get().to_dict().get("parameters")
    pos_file_uploaded = google_cloud_storage.check_file_exists("pos.txt")
    if request.method == "GET":
        return render_template(
            "gwas/parameters.html",
            study_title=study_title,
            parameters=parameters,
            pos_file_uploaded=pos_file_uploaded,
        )
    elif "save" in request.form:
        for p in parameters["index"]:
            parameters[p]["value"] = request.form.get(p)
        doc_ref.set({"parameters": parameters}, merge=True)
        return redirect(url_for("gwas.start", study_title=study_title))
    elif "upload" in request.form:
        file = request.files["file"]
        if file.filename == "":
            r = redirect(url_for("gwas.parameters", study_title=study_title))
            flash(r, "Please select a file to upload.")
            return r
        elif file and file.filename == "pos.txt":
            gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
            gcloudStorage.upload_to_bucket(file, file.filename)
            return redirect(url_for("gwas.start", study_title=study_title))
        else:
            r = redirect(url_for("gwas.parameters", study_title=study_title))
            flash(r, "Please upload a valid pos.txt file.")
            return r
    else:
        print("Unknown request")
        exit(1)


@bp.route("/personal_parameters/<study_title>", methods=("GET", "POST"))
def personal_parameters(study_title):
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    parameters = doc_ref.get().to_dict().get("personal_parameters")

    if request.method == "GET":
        return render_template(
            "gwas/personal_parameters.html",
            study_title=study_title,
            parameters=parameters[g.user["id"]],
        )

    for p in parameters[g.user["id"]]["index"]:
        if p in request.form:
            parameters[g.user["id"]][p]["value"] = request.form.get(p)
    doc_ref.set({"personal_parameters": parameters}, merge=True)
    return redirect(url_for("gwas.start", study_title=study_title))


# def get_status(role: str, gcp_project, status, project_title):
#     if status == "GWAS Completed!":
#         return status

#     gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, project_title)
#     gcloudCompute = GoogleCloudCompute(gcp_project)
#     status = gcloudPubsub.listen_to_startup_script(status)

#     if status == "GWAS Completed!":
#         instance = (
#             project_title.replace(" ", "").lower()
#             + "-"
#             + constants.INSTANCE_NAME_ROOT
#             + role
#         )
#         gcloudCompute.stop_instance(constants.ZONE, instance)
#         gcloudPubsub.delete_topic()
#     return status


def run_gwas(role: str, gcp_project: str, study_title: str, vm_parameters=None) -> None:
    gcloudCompute = GoogleCloudCompute(gcp_project)
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, study_title)

    # copy parameters to parameter files
    gcloudStorage.copy_parameters_to_bucket(study_title, role)

    instance = create_instance_name(study_title, role)
    gcloudCompute.setup_networking(role)
    gcloudCompute.setup_instance(
        constants.ZONE,
        instance,
        role,
        vm_parameters["NUM_CPUS"]["value"],
        metadata={"key": "bucketname", "value": vm_parameters["BUCKET_NAME"]["value"]},
        boot_disk_size=vm_parameters["BOOT_DISK_SIZE"]["value"],
    )

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
