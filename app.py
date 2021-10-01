
import os
import sys

from flask import Flask, flash, redirect, render_template, request, url_for
from waitress import serve

import constants
from utils.google_cloud.google_cloud_compute import GoogleCloudCompute

app = Flask(__name__)
app.secret_key = os.urandom(12).hex()


@app.route("/", methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        project: str = request.form['project']
        if not project:
            flash("Project is required")

        gcloudCompute = GoogleCloudCompute(project)

        role: str = request.form['role']
        if not role:
            flash("Role is required")
        else:
            instance = constants.INSTANCE_NAME_ROOT + str(role)

            # Check/Set-up correct network, subnet, and firewall
            gcloudCompute.validate_networking()

            # Check/Set-up correct VM instance(s)
            gcloudCompute.validate_instance(instance, role)

            print("I've done what I can.  GWAS should be running now.")
            return "I love gwas so much!"

    return render_template('home.html', project=constants.SERVER_PROJECT_NAME)


if __name__ == "__main__":
    p = 5000
    if len(sys.argv) > 1:
        p = sys.argv[1]
    serve(app, port=p)
    # app.run(debug=False, port=p)
