import os
import secrets

import firebase_admin
from google.cloud import firestore
from quart import Quart, json
from quart_cors import cors
from werkzeug.exceptions import HTTPException

from src import cli, signaling, status
from src.api_utils import get_allowed_origins
from src.auth import register_terra_service_account
from src.utils import constants, custom_logging
from src.web import participants, study, web

logger = custom_logging.setup_logging(__name__)


def create_app() -> Quart:
    if constants.TERRA:
        logger.info("Creating app - on Terra")
    else:
        logger.info("Creating app - NOT on Terra")

    initialize_firebase_app()

    app = Quart(__name__)

    app = cors(app, allow_origin=get_allowed_origins())

    app.config.from_mapping(
        SECRET_KEY=secrets.token_hex(16),
        DATABASE=firestore.AsyncClient(
            project=constants.FIREBASE_PROJECT_ID,
            database=constants.FIRESTORE_DATABASE,
        ),
    )

    app.register_blueprint(status.bp)
    app.register_blueprint(cli.bp)
    app.register_blueprint(web.bp)
    app.register_blueprint(participants.bp)
    app.register_blueprint(study.bp)
    app.register_blueprint(signaling.bp)

    @app.before_serving
    async def _register_terra_service_account():
        if constants.TERRA:
            await register_terra_service_account()

    @app.errorhandler(HTTPException)
    async def handle_exception(e: HTTPException):
        res = e.get_response()
        if e.description:
            res.data = json.dumps({"error": e.description})  # type: ignore
            res.content_type = "application/json"
        return res

    return app


def initialize_firebase_app() -> None:
    key: str = ".serviceAccountKey.json"
    options = {
        "projectId": constants.FIREBASE_PROJECT_ID,
    }
    if os.path.exists(key):  # local testing
        firebase_admin.initialize_app(credential=firebase_admin.credentials.Certificate(key), options=options)
    else:
        logger.info("No service account key found, using default for firebase_admin")
        firebase_admin.initialize_app(options=options)

    # test firestore connection
    logger.info(f"Using firestore database: {constants.FIRESTORE_DATABASE}")
    db = firestore.Client(project=constants.FIREBASE_PROJECT_ID, database=constants.FIRESTORE_DATABASE)
    logger.info(f'Firestore test: {db.collection("test").document("test").get().exists}')
