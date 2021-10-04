
import os
import sys

from flask import Flask, redirect, render_template, request, url_for
from waitress import serve

import constants
from utils.google_cloud.google_cloud_compute import GoogleCloudCompute

app = Flask(__name__)
app.secret_key = os.urandom(12).hex()


@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        role: str = request.form['role']
        project: str = request.form['project']

        global gcloudCompute
        gcloudCompute = GoogleCloudCompute(project)

        instance = constants.INSTANCE_NAME_ROOT + role

        # Validate/Set-up correct network, subnet, and firewall
        gcloudCompute.validate_networking()

        # Set-up correct VM instance(s)
        gcloudCompute.create_instance(constants.ZONE, instance, role)

        print("I've done what I can.  GWAS should be running now.")
        return redirect(url_for("running", role=role))

    return render_template('home.html', project=constants.SERVER_PROJECT_NAME)

@app.route("/running/<role>", methods=['GET', 'POST'])
def running(role):
    gcloudCompute.listen_to_startup_script(role)
    return render_template('running.html', status=constants.STATUS)

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else 5000
    serve(app, port=p)
