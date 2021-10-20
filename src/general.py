from flask import Blueprint, render_template
from google.cloud import firestore

bp = Blueprint("general", __name__)
db = firestore.Client()


@bp.route("/")
@bp.route("/home")
def home():
    return render_template("home.html")


@bp.route("/workflow")
def workflow():
    return render_template("workflow.html")
