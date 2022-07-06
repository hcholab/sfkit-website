import re

from flask import current_app, redirect, url_for
from src.utils import constants
from src.utils.generic_functions import redirect_with_flash
from werkzeug import Response


def valid_study_title(study_title: str, type: str) -> tuple[bool, Response]:
    if not re.match(r"^[a-zA-Z][ a-zA-Z0-9-]*$", study_title):
        return (
            False,
            redirect_with_flash(
                url=url_for("studies.create_study", type=type),
                message="Title can include only letters, numbers, spaces, and dashes, and must start with a letter.",
            ),
        )

    # validate that title is unique
    db = current_app.config["DATABASE"]
    studies = db.collection("studies").stream()
    for study in studies:  # sourcery skip: use-next
        if study.to_dict()["title"].replace(" ", "").lower() == study_title.replace(" ", "").lower():
            return (
                False,
                redirect_with_flash(
                    url=url_for("studies.create_study", type=type),
                    message="Title already exists.",
                ),
            )

    return (True, redirect(url_for("studies.parameters", study_title=study_title)))


def create_instance_name(study_title: str, role: str) -> str:
    return f"{study_title.replace(' ', '').lower()}-{constants.INSTANCE_NAME_ROOT}{role}"


def data_has_valid_size(size: int, doc_ref_dict: dict, role: int) -> bool:
    user_id: str = doc_ref_dict["participants"][role]
    num_snps: int = int(doc_ref_dict["parameters"]["NUM_SNPS"].get("value", "0"))
    num_inds: int = int(doc_ref_dict["personal_parameters"][user_id]["NUM_INDS"].get("value", "0"))

    estimated_size: int = num_snps * num_inds * constants.DATA_VALIDATION_CONSTANT

    if size > 2 * estimated_size or size < estimated_size / 2:
        print(f"Validation has failed.  The size is {size} and the estimated size is {estimated_size}.")
        return False

    return True


def data_has_valid_files(files: str) -> bool:
    return all(desired_file in files for desired_file in constants.DATA_VALIDATION_FILES)
