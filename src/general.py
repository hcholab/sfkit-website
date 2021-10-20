from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from google.cloud import firestore
from google.protobuf import descriptor

from src import constants
from src.auth import login_required
from src.utils.google_cloud.google_cloud_compute import GoogleCloudCompute
from src.utils.google_cloud.google_cloud_pubsub import GoogleCloudPubsub

bp = Blueprint("general", __name__)
db = firestore.Client()


@bp.route("/")
@bp.route("/home")
def home():
    return render_template("home.html")


@bp.route("/workflow")
def workflow():
    return render_template("workflow.html")
