import os
import sys
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for
from waitress import serve

import constants
from utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from utils.google_cloud.google_cloud_pubsub import GoogleCloudPubsub
from utils.google_cloud.google_cloud_storage import GoogleCloudStorage

app = Flask(__name__)
app.secret_key = os.urandom(12).hex()


@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == "GET":
        return render_template('home.html', project=constants.SERVER_PROJECT)
    elif request.method == 'POST':
        role: str = request.form['role']
        project: str = request.form['project']

        gcloudCompute = GoogleCloudCompute(project)
        gcloudStorage = GoogleCloudStorage(constants.SERVER_PROJECT)
        gcloudPubsub = GoogleCloudPubsub(constants.SERVER_PROJECT, role)

        gcloudPubsub.create_topic_and_subscribe()

        instance = constants.INSTANCE_NAME_ROOT + role

        gcloudCompute.setup_networking(role)

        _ = gcloudCompute.setup_instance(constants.ZONE, instance, role)

        # Give instance publish access to pubsub for status updates
        member = "serviceAccount:" + \
            gcloudCompute.get_service_account_for_vm(
                zone=constants.ZONE, instance=instance)
        gcloudPubsub.add_pub_iam_member("roles/pubsub.publisher", member)

        # # Create bucket to store the ip addresses; this will be read-only for the VMs
        # bucket = gcloudStorage.validate_bucket(role)
        # blob = bucket.blob("ip_addresses/P" + role)
        # blob.upload_from_string(vm_external_ip_address)

        # # Give the instance's service account read-access to this bucket
        # gcloudStorage.add_bucket_iam_member(
        #     constants.BUCKET_NAME, "roles/storage.objectViewer", member)

        print("I've done what I can.  GWAS should be running now.")
        initial_status = "Setting up the Virtual Machine instance at " + \
            str(datetime.now())
        return redirect(url_for("running", project=project, role=role, status=initial_status))


@app.route("/running/<project>/<role>/<status>", methods=['GET', 'POST'])
def running(project, role, status):
    gcloudPubsub = GoogleCloudPubsub(constants.SERVER_PROJECT, role)
    gcloudCompute = GoogleCloudCompute(project)
    status = gcloudPubsub.listen_to_startup_script(status)

    if status.split(" ")[0] == "GWAS_completed":
        gcloudCompute.stop_instance(
            constants.ZONE, constants.INSTANCE_NAME_ROOT + role)
        return "GWAS completed; yay!"
    elif (status.split(" ")[0] == "DataSharing_completed" and role == "3"):
        gcloudCompute.test_ssh(constants.INSTANCE_NAME_ROOT + role) # TODO: remove after testing
        gcloudCompute.stop_instance(
            constants.ZONE, constants.INSTANCE_NAME_ROOT + role)
        return "DataSharing completed; yay!"

    return render_template('running.html', role=role, status=status)


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else 5000
    serve(app, port=p)
