from time import sleep

from flask import Blueprint, current_app, g, redirect, url_for
from werkzeug import Response

from src.auth import login_required

bp = Blueprint("pca", __name__, url_prefix="/pca")


@bp.route("/validate_data/<study_title>")
@login_required
def validate_data(study_title: str) -> Response:
    sleep(2)

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["status"][g.user["id"]] = ["not ready"]
    doc_ref.set(doc_ref_dict)

    return redirect(url_for("studies.study", study_title=study_title))


@bp.route("/start_protocol/<study_title>", methods=["POST"])
@login_required
def start_protocol(study_title: str) -> Response:
    sleep(2)

    db = current_app.config["DATABASE"]
    doc_ref = db.collection("studies").document(study_title.replace(" ", "").lower())
    doc_ref_dict = doc_ref.get().to_dict()
    doc_ref_dict["status"][g.user["id"]] = ["PCA is now running!"]
    doc_ref.set(doc_ref_dict)

    return redirect(url_for("studies.study", study_title=study_title))
