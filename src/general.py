from flask import Blueprint, render_template

bp = Blueprint("general", __name__)


@bp.route("/")
@bp.route("/home")
def home():
    return render_template("home.html")


@bp.route("/workflow")
def workflow():
    return render_template("workflow.html")
