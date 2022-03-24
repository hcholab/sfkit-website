from flask import Blueprint, current_app, g, redirect, request, url_for
from werkzeug import Response

from src.auth import login_required
from src.utils import constants
from src.utils.generic_functions import redirect_with_flash
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM
from src.utils.google_cloud.google_cloud_pubsub import GoogleCloudPubsub
from src.utils.google_cloud.google_cloud_storage import GoogleCloudStorage
from src.utils.gwas_functions import create_instance_name

bp = Blueprint("gwas", __name__)


@bp.route("/validate_data/<study_title>")
@login_required
def validate_data(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    role: str = str(doc_ref_dict["participants"].index(g.user["id"]) + 1)
    gcp_project = doc_ref_dict["personal_parameters"][g.user["id"]]["GCP_PROJECT"]["value"]
    data_path = doc_ref_dict["personal_parameters"][g.user["id"]]["DATA_PATH"]["value"]
    if not gcp_project or gcp_project == "" or not data_path or data_path == "":
        return redirect_with_flash(
            url=url_for("studies.personal_parameters", study_title=study_title),
            message="Please set your GCP project and storage bucket location.",
        )

    statuses = doc_ref_dict["status"]
    statuses[g.user["id"]] = ["validating"]
    doc_ref.set({"status": statuses}, merge=True)

    if role == "1":
        # setup networking for CP0 as well
        gcloudCompute = GoogleCloudCompute(constants.SERVER_GCP_PROJECT)
        gcloudCompute.setup_networking(doc_ref_dict, "0")

    gcloudCompute = GoogleCloudCompute(gcp_project)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, study_title)

    gcloudPubsub.create_topic_and_subscribe()
    instance = create_instance_name(study_title, role)
    gcloudCompute.setup_networking(doc_ref_dict, role)
    gcloudCompute.setup_instance(
        constants.SERVER_ZONE, instance, role, {"key": "data_path", "value": data_path}, validate=True
    )

    # Give instance publish access to pubsub for status updates
    member = "serviceAccount:" + gcloudCompute.get_service_account_for_vm(
        zone=constants.SERVER_ZONE, instance=instance
    )
    gcloudPubsub.add_pub_iam_member("roles/pubsub.publisher", member)

    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/start_gwas/<study_title>", methods=["POST"])
@login_required
def start_gwas(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    user_id = g.user["id"]
    role: int = doc_ref_dict["participants"].index(user_id) + 1
    gcp_project = doc_ref_dict["personal_parameters"][user_id]["GCP_PROJECT"]["value"]
    statuses = doc_ref_dict["status"]

    if statuses[user_id] == ["not ready"]:
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

    if any(s in str(statuses.values()) for s in ["['']", "['validating']", "['invalid data']", "['not ready']"]):
        pass
    elif statuses[user_id] == ["ready"]:
        statuses[user_id] = ["setting up your vm instance"]

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
            vm_parameters = doc_ref_dict["personal_parameters"][user_id]
            gcloudCompute.setup_instance(
                constants.SERVER_ZONE,
                instance,
                "0",
                {"key": "data_path", "value": "secure-gwas-data0"},
                vm_parameters["NUM_CPUS"]["value"],
                boot_disk_size=vm_parameters["BOOT_DISK_SIZE"]["value"],
            )
        run_gwas(
            str(role),
            gcp_project,
            study_title,
            doc_ref_dict["personal_parameters"][user_id],
        )

    return redirect(url_for("studies.study", study_title=study_title))


def run_gwas(role: str, gcp_project: str, study_title: str, vm_parameters: dict) -> None:
    gcloudCompute = GoogleCloudCompute(gcp_project)
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, study_title)

    # copy parameters to parameter files
    gcloudStorage.copy_parameters_to_bucket(study_title, role)

    instance = create_instance_name(study_title, role)
    gcloudCompute.setup_instance(
        constants.SERVER_ZONE,
        instance,
        role,
        {"key": "data_path", "value": vm_parameters["DATA_PATH"]["value"]},
        vm_parameters["NUM_CPUS"]["value"],
        boot_disk_size=vm_parameters["BOOT_DISK_SIZE"]["value"],
    )

    # Give instance publish access to pubsub for status updates
    member = "serviceAccount:" + gcloudCompute.get_service_account_for_vm(
        zone=constants.SERVER_ZONE, instance=instance
    )
    gcloudPubsub.add_pub_iam_member("roles/pubsub.publisher", member)
    # give instance read access to storage buckets for parameter files
    gcloudStorage.add_bucket_iam_member(constants.PARAMETER_BUCKET, "roles/storage.objectViewer", member)

    print("I've done what I can.  GWAS should be running now.")
