from flask import redirect, url_for
from werkzeug import Response
from src import constants


def redirect_with_flash(location: str, message: str, error: str = "") -> Response:
    r = redirect(url_for(location))
    print(f"{message}: {error}") if error else print(message)
    flash(r, message)
    return r


def flash(response, message):
    response.set_cookie("flash", message)
    return response


def create_instance_name(study_title, role):
    return (
        f"{study_title.replace(' ', '').lower()}-{constants.INSTANCE_NAME_ROOT}{role}"
    )


def validate(size: int, doc_ref_dict: dict, role: int) -> bool:
    id: str = doc_ref_dict.get("participants", [])[role - 1]
    num_snps: int = int(
        doc_ref_dict.get("parameters", {}).get("NUM_SNPS", {}).get("value", "0")
    )
    num_inds: int = int(
        doc_ref_dict.get("personal_parameters", {})
        .get(id, {})
        .get("NUM_INDS", {})
        .get("value", "0")
    )

    estimated_size: int = num_snps * num_inds * constants.DATA_VALIDATION_CONSTANT

    if size > 2 * estimated_size or size < estimated_size / 2:
        print(
            f"Validation has failed.  The size is {size} and the estimated size is {estimated_size}."
        )
        return False

    return True
