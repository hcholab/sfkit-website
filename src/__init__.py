import os

import firebase_admin
from flask import Flask
from flask_bootstrap import Bootstrap
from google.cloud import firestore


def create_app():
    app = Flask(__name__)

    firebase_admin.initialize_app(
        # firebase_admin.credentials.Certificate("serviceAccountKey.json")
    )

    app.config.from_mapping(
        SECRET_KEY=os.urandom(12).hex(), DATABASE=firestore.Client()
    )

    Bootstrap(app)

    from src import auth, general, gwas

    app.register_blueprint(auth.bp)
    app.register_blueprint(gwas.bp)
    app.register_blueprint(general.bp)

    return app
