import pytest
from src import create_app
from mockfirestore import MockFirestore
import os


@pytest.fixture
def app():
    return create_app(
        {
            "SECRET_KEY": os.urandom(12).hex(),
            "TESTING": True,
            "DATABASE": MockFirestore(),
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()
