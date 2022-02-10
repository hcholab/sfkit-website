import os

import firebase_admin
from flask import Flask
from flask_bootstrap import Bootstrap
from google.cloud import firestore


def create_app():
    app = Flask(__name__)

    # if serviceAccountKey.json file exists, use it to initialize the app
    if os.path.exists("serviceAccountKey.json"):
        print("Using serviceAccountKey.json for the firebase_admin")
        firebase_admin.initialize_app(
            firebase_admin.credentials.Certificate("serviceAccountKey.json")
        )
    else:
        print("Using default service account for the firebase_admin")
        firebase_admin.initialize_app()

    app.config.from_mapping(
        SECRET_KEY=os.urandom(12).hex(), DATABASE=firestore.Client()
    )

    Bootstrap(app)

    from src import auth, general, gwas

    app.register_blueprint(auth.bp)
    app.register_blueprint(gwas.bp)
    app.register_blueprint(general.bp)

    return app
