import os
import secrets

import firebase_admin
from quart import Quart
from quart_cors import cors
from google.cloud import firestore

from src import cli, signaling, status
from src.utils import constants, custom_logging
from src.web import web, participants, study

logger = custom_logging.setup_logging(__name__)


def create_app() -> Quart:
    if constants.TERRA:
        logger.info("Creating app - on Terra")
    else:
        logger.info("Creating app - NOT on Terra")

    firebase_app = initialize_firebase_app()

    app = Quart(__name__)

    origins = filter(None, os.getenv("CORS_ORIGINS", "*").split(","))
    app = cors(app, allow_origin=list(origins))

    app.config.from_mapping(
        SECRET_KEY=secrets.token_hex(16),
        DATABASE=firestore.AsyncClient(project=firebase_app.project_id),
    )

    app.register_blueprint(status.bp)
    app.register_blueprint(cli.bp)
    app.register_blueprint(web.bp)
    app.register_blueprint(participants.bp)
    app.register_blueprint(study.bp)
    app.register_blueprint(signaling.bp)

    return app


def initialize_firebase_app() -> firebase_admin.App:
    key: str = ".serviceAccountKey.json"
    options = { 'projectId': constants.FIREBASE_PROJECT_ID}
    if os.path.exists(key):  # local testing
        app = firebase_admin.initialize_app(credential=firebase_admin.credentials.Certificate(key),
                                            options=options)
    else:
        logger.info("No service account key found, using default for firebase_admin")
        app = firebase_admin.initialize_app(options=options)

    # test firestore connection
    db = firestore.Client(project=app.project_id)
    logger.info(f'Firestore test: {db.collection("test").document("test").get().exists}')
    return app
