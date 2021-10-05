
import os
import sys

from flask import Flask, redirect, render_template, request, url_for
from waitress import serve

import constants
from utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from utils.google_cloud.google_cloud_storage import GoogleCloudStorage

app = Flask(__name__)
app.secret_key = os.urandom(12).hex()



@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == "GET":
        return render_template('home.html', project=constants.SERVER_PROJECT)
    elif request.method == 'POST':
        role: str = request.form['role']
        constants.CLIENT_PROJECT = request.form['project']

        gcloudCompute = GoogleCloudCompute(constants.CLIENT_PROJECT)
        gcloudStorage = GoogleCloudStorage(constants.SERVER_PROJECT)

        instance = constants.INSTANCE_NAME_ROOT + role

        # Validate/Set-up correct network, subnet, firewall, and peering
        gcloudCompute.validate_networking()

        # Set-up correct VM instance(s)
        gcloudCompute.create_instance(constants.ZONE, instance, role)
        vm_external_ip_address = gcloudCompute.get_vm_external_ip_address(constants.ZONE, instance)

        # Create bucket to store the ip addresses; this will be read-only for the VMs
        bucket = gcloudStorage.validate_bucket()
        blob = bucket.blob("ip_addresses/P" + role)
        blob.upload_from_string(vm_external_ip_address)

        # Give the instance's service account read-access to this bucket
        member = "serviceAccount:" + gcloudCompute.get_service_account_for_vm(zone=constants.ZONE, instance=instance)
        gcloudStorage.add_bucket_iam_member(constants.BUCKET_NAME, "roles/storage.objectViewer", member)

        print("I've done what I can.  GWAS should be running now.")
        return redirect(url_for("running", role=role))


@app.route("/running/<role>", methods=['GET', 'POST'])
def running(role):
    gcloudCompute = GoogleCloudCompute(constants.CLIENT_PROJECT)
    gcloudCompute.listen_to_startup_script(role)
    return render_template('running.html', status=constants.STATUS)

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else 5000
    serve(app, port=p)
