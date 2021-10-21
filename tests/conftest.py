import os
import tempfile

import pytest
from src import create_app
from mockfirestore import MockFirestore

@pytest.fixture
def app():
    return create_app({
            "TESTING": True,
            "DATABASE": MockFirestore()})


@pytest.fixture
def client(app):
    return app.test_client()
