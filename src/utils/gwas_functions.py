import re

from flask import current_app, redirect, url_for
from src.utils import constants
from src.utils.generic_functions import redirect_with_flash
from werkzeug import Response


def valid_study_title(study_title: str, study_type: str, setup_configuration: str) -> tuple[bool, Response]:
    if not re.match(r"^[a-zA-Z][ a-zA-Z0-9-]*$", study_title):
        return (
            False,
            redirect_with_flash(
                url=url_for("studies.create_study", study_type=study_type, setup_configuration=setup_configuration),
                message="Title can include only letters, numbers, spaces, and dashes, and must start with a letter.",
            ),
        )

    # validate that title is unique
    db = current_app.config["DATABASE"]
    studies = db.collection("studies").stream()
    for study in studies:
        if study.to_dict()["title"].replace(" ", "").lower() == study_title.replace(" ", "").lower():
            return (
                False,
                redirect_with_flash(
                    url=url_for(
                        "studies.create_study", study_type=study_type, setup_configuration=setup_configuration
                    ),
                    message="Title already exists.",
                ),
            )

    return (True, redirect(url_for("studies.parameters", study_title=study_title)))


def create_instance_name(study_title: str, role: str) -> str:
    return f"{study_title.replace(' ', '').lower()}-{constants.INSTANCE_NAME_ROOT}{role}"
