import os
import secrets

import firebase_admin
import google
import google.oauth2.id_token
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request
from google.cloud import firestore
from quart import Quart
from quart_cors import cors

from src import cli, signaling, status
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

    origins = filter(None, os.getenv("CORS_ORIGINS", "*").split(","))
    app = cors(app, allow_origin=list(origins))

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

    return app


def initialize_firebase_app() -> None:
    key: str = ".serviceAccountKey.json"
    options = {
        'projectId': constants.FIREBASE_PROJECT_ID,
    }
    if os.path.exists(key):  # local testing
        firebase_admin.initialize_app(credential=firebase_admin.credentials.Certificate(key),
                                            options=options)
    else:
        logger.info("No service account key found, using default for firebase_admin")
        cred = firebase_admin.credentials.ApplicationDefault()
        if constants.TARGET_SERVICE_ACCOUNT:
            gcred, _ = google.auth.default()

            # for testing
            aud = "https://iam.googleapis.com"
            token = google.oauth2.id_token.fetch_id_token(Request(), aud)
            logger.info(f'Default Google token: {".".join(token.split(".")[:2])}')

            gcred = impersonated_credentials.Credentials(
                source_credentials=gcred,
                target_principal=constants.TARGET_SERVICE_ACCOUNT,
                target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                lifetime=500)

            # for testing
            token = google.oauth2.id_token.fetch_id_token(Request(), aud)
            logger.info(f'Impersonated Google token: {".".join(token.split(".")[:2])}')

            # https://github.com/firebase/firebase-admin-python/issues/698
            cred._g_credential = gcred
            cred._project_id = constants.FIREBASE_PROJECT_ID
            options['serviceAccountId'] = constants.TARGET_SERVICE_ACCOUNT

            # for testing
            token = cred.get_access_token().access_token
            logger.info(f'Impersonated Firebase token: {".".join(token.split(".")[:2])}')

        firebase_admin.initialize_app(credential=cred, options=options)

    # test firestore connection
    db = firestore.Client(project=constants.FIREBASE_PROJECT_ID,
                          database=constants.FIRESTORE_DATABASE)
    logger.info(f'Firestore test: {db.collection("test").document("test").get().exists}')
