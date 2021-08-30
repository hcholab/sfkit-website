
import os
import time

from flask import Flask, flash, redirect, render_template, request, url_for
from waitress import serve

import constants
from utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from utils.google_cloud.google_cloud_storage import GoogleCloudStorage

app = Flask(__name__)

gcloudCompute = GoogleCloudCompute(constants.PROJECT_NAME)
gcloudStorage = GoogleCloudStorage(constants.PROJECT_NAME)


@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        role = request.form['role']

        if not role:
            flash("Role is required")
        else:
            instance = constants.INSTANCE_NAME_ROOT + str(role)

            # Check/Set-up correct network, subnet, and firewall
            gcloudCompute.validate_networking()

            # Check/Set-up correct VM instance(s)
            vm_external_ip_address = gcloudCompute.validate_instance(instance)

            # Check/Set-up correct Storage bucket(s)
            bucket = gcloudStorage.validate_buckets()

            # Put IP address in bucket for all to see...
            blob = bucket.blob("ip_addresses/IP_ADDR_P" + role)
            blob.upload_from_string(vm_external_ip_address)

            return redirect(url_for("start_gwas", project=constants.PROJECT_NAME, instance=instance, role=role))

    return render_template('home.html', project=constants.PROJECT_NAME)


@app.route("/start_gwas/<string:project>/<string:instance>/<string:role>", methods=['GET'])
def start_gwas(project, instance, role):
    # TODO: make peerings? - only necessary for working with distinct projects

    ip_addresses = gcloudStorage.get_ip_addresses_from_bucket()
    time.sleep(1 + 5 * int(role))

    # Update parameter files on instaces with correct ip addresses
    gcloudCompute.update_ip_addresses_on_vm(ip_addresses, instance, role)
    time.sleep(1 + 10 * int(role))

    # Run Data Sharing Client
    gcloudCompute.run_data_sharing(instance, role)
    print("\n\nSLEEPING FOR A COUPLE OF MINUTES; PLEASE TAKE THIS TIME TO EAT SOME CHOCOLATE\n\n")
    time.sleep(120 + 15 * int(role))

    # Run GWAS client
    gcloudCompute.run_gwas_client(instance, role)

    # Clean up IP_Addresses
    gcloudStorage.delete_blob(constants.BUCKET_NAME,
                              "ip_addresses/IP_ADDR_P" + role)

    # Stop running instances
    gcloudCompute.stop_instance(project, constants.ZONE, instance)

    return "I love gwas so much!"


if __name__ == "__main__":
    app.secret_key = os.urandom(12).hex()

    # p = 5000
    # if len(sys.argv) > 1:
    #     p = sys.argv[1]
    # # serve(app, host="127.0.0.1", port=p)
    # p = os.environ.get('PORT')
    serve(app, port=5000)
    # app.run(debug=False, port=p)

    # app.run()
