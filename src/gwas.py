from flask import (
    Blueprint,
    current_app,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug import Response

from src import constants
from src.auth import login_required
from src.utils.generic_functions import redirect_with_flash, flash
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from src.utils.google_cloud.google_cloud_iam import GoogleCloudIAM
from src.utils.google_cloud.google_cloud_pubsub import GoogleCloudPubsub
from src.utils.google_cloud.google_cloud_storage import GoogleCloudStorage
from src.utils.gwas_functions import create_instance_name

bp = Blueprint("gwas", __name__)


@bp.route("/validate_bucket/<study_title>")
@login_required
def validate_bucket(study_title: str) -> Response:
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
        return redirect_with_flash(
            location="studies.personal_parameters",
            message="Please set your GCP project and storage bucket location.",
        )

    statuses = doc_ref_dict["status"]
    statuses[g.user["id"]] = ["validating"]
    doc_ref.set({"status": statuses}, merge=True)

    if role == "1":
        # setup networking for CP0 as well
        gcloudCompute = GoogleCloudCompute(constants.SERVER_GCP_PROJECT)
        gcloudCompute.setup_networking("0")

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

    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/start_gwas/<study_title>", methods=["POST"])
@login_required
def start_gwas(study_title: str) -> Response:
    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    id = g.user["id"]
    role: int = doc_ref_dict["participants"].index(id) + 1
    gcp_project = doc_ref_dict["personal_parameters"][id]["GCP_PROJECT"]["value"]
    statuses = doc_ref_dict["status"]

    # check if pos.txt is in the google cloud bucket
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    if not gcloudStorage.check_file_exists("pos.txt"):
        message = "Please upload a pos.txt file or have one of the entities you are runnning this study with do so for you."
        r = redirect(
            url_for("studies.parameters", study_title=study_title, section="pos")
        )
        flash(r, message)
        return r

    if statuses[id] == ["not ready"]:
        if not GoogleCloudIAM().test_permissions(gcp_project):
            return redirect_with_flash(
                location="general.permissions",
                message="Please give the service appropriate permissions first.",
            )

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
            # gcloudCompute.setup_networking("0")
            gcloudCompute.setup_instance(
                constants.ZONE,
                instance,
                "0",
                vm_parameters["NUM_CPUS"]["value"],
                metadata={
                    "key": "bucketname",
                    "value": "secure-gwas-data0",
                },
                boot_disk_size=vm_parameters["BOOT_DISK_SIZE"]["value"],
            )
        run_gwas(
            str(role),
            gcp_project,
            study_title,
            vm_parameters=doc_ref_dict["personal_parameters"][id],
        )

    return redirect(url_for("studies.study", study_title=study_title))


def run_gwas(
    role: str, gcp_project: str, study_title: str, vm_parameters: dict = dict()
) -> None:
    gcloudCompute = GoogleCloudCompute(gcp_project)
    gcloudStorage = GoogleCloudStorage(constants.SERVER_GCP_PROJECT)
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_GCP_PROJECT, role, study_title)

    # copy parameters to parameter files
    gcloudStorage.copy_parameters_to_bucket(study_title, role)

    instance = create_instance_name(study_title, role)
    # gcloudCompute.setup_networking(role)
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

    print("I've done what I can.  GWAS should be running now.")
