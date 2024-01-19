from typing import Tuple

from quart import Blueprint

from src.utils import constants

bp = Blueprint("status", __name__, url_prefix="")


@bp.route("/status", methods=["GET"])
async def status() -> Tuple[dict, int]:
    return {}, 200


@bp.route("/version", methods=["GET"])
async def version() -> Tuple[dict, int]:
    return {"appVersion": constants.APP_VERSION, "buildVersion": constants.BUILD_VERSION}, 200
