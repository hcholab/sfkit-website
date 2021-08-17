import sys

import googleapiclient.discovery
from flask import Flask, flash, redirect, render_template, request, url_for
from google.cloud import storage
from waitress import serve

import constants
from google_cloud_functions import *

app = Flask(__name__)

compute = googleapiclient.discovery.build('compute', 'v1')


@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        role = request.form['role']

        if not role:
            flash("Role is required")
        else:
            instance = constants.INSTANCE_NAME_ROOT + str(role)

            # Check for correct network and subnet
            existing_nets = [net['name'] for net in compute.networks().list(
                project=constants.PROJECT_NAME).execute()['items']]
            if constants.NETWORK_NAME not in existing_nets:
                create_network(compute, constants.PROJECT_NAME, constants.NETWORK_NAME)
                create_subnet(compute, constants.PROJECT_NAME, constants.REGION, constants.NETWORK_NAME)
                create_firewalls(compute, constants.PROJECT_NAME, constants.NETWORK_NAME)

            existing_instances = list_instances(compute, constants.PROJECT_NAME, constants.ZONE)
            if not existing_instances or instance not in existing_instances:
                create_instance(compute, constants.PROJECT_NAME, constants.ZONE, instance)

            start_instance(compute, constants.PROJECT_NAME, constants.ZONE, instance)
            time.sleep(5)

            vm_external_ip_address = get_vm_external_ip_address(
                compute, constants.PROJECT_NAME, constants.ZONE, instance)
            storage_client = storage.Client(project=constants.PROJECT_NAME)
            buckets = [bucket.name for bucket in storage_client.list_buckets()]

            if constants.BUCKET_NAME not in buckets:
                storage_client.create_bucket(constants.BUCKET_NAME)
                time.sleep(1)

            bucket = storage_client.bucket(constants.BUCKET_NAME)
            blob = bucket.blob("ip_addresses/IP_ADDR_P" + role)
            blob.upload_from_string(vm_external_ip_address)

            return redirect(url_for("start_gwas", project=constants.PROJECT_NAME, instance=instance, role=role))

    return render_template('home.html', project=constants.PROJECT_NAME)


@app.route("/start_gwas/<string:project>/<string:instance>/<string:role>", methods=['GET'])
def start_gwas(project, instance, role):
    # TODO: make peerings? - only necessary for working with distinct projects

    ip_addresses = get_ip_addresses_from_bucket()

    time.sleep(1 + 5 * int(role))

    cmds = [
        'cd ~/secure-gwas; rm log/*; rm cache/*'
    ]
    for (k, v) in ip_addresses:
        cmds.append(
            'sed -i "s|^{k}.*$|{k} {v}|g" ~/secure-gwas/par/test.par.{role}.txt'.format(k=k, v=v, role=role))
    execute_shell_script_on_instance(project, instance, cmds)

    time.sleep(1 + 10 * int(role))

    cmds = []
    if str(role) != "3":
        cmds = [
            'cd ~/secure-gwas/code',
            'bin/DataSharingClient {role} ../par/test.par.{role}.txt'.format(
                role=role),
            'echo completed DataSharing',
        ]
    else:
        cmds = [
            'cd ~/secure-gwas/code',
            'bin/DataSharingClient {role} ../par/test.par.{role}.txt ../test_data/'.format(
                role=role),
            'echo completed'
        ]

    execute_shell_script_on_instance(project, instance, cmds)

    print("\n\nSLEEPING FOR A COUPLE OF MINUTES; PLEASE TAKE THIS TIME TO EAT SOME CHOCOLATE\n\n")
    time.sleep(120 + 15 * int(role))

    cmds = []
    if str(role) != "3":
        cmds = [
            'cd ~/secure-gwas/code',
            'bin/GwasClient {role} ../par/test.par.{role}.txt'.format(
                role=role),
            'echo completed GwasClient',
        ]
        execute_shell_script_on_instance(project, instance, cmds)

    delete_blob(constants.BUCKET_NAME, "ip_addresses/IP_ADDR_P" + role)
    stop_instance(compute, project, constants.ZONE, instance)

    return "I love gwas so much!"


if __name__ == "__main__":
    app.secret_key = os.urandom(12).hex()

    # p = 5000
    # if len(sys.argv) > 1:
    #     p = sys.argv[1]
    # # serve(app, host="127.0.0.1", port=p)
    # p = os.environ.get('PORT')
    serve(app, port=8080)
    # app.run(debug=False, port=p)

    # app.run()
