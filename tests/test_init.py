from typing import Callable, Generator

from pytest_mock import MockerFixture

from src import initialize_firebase_admin


def test_initialize_firebase_admin(mocker: Callable[..., Generator[MockerFixture, None, None]]):
    mocker.patch("src.os.path.exists", return_value=False)
    mocker.patch("src.firebase_admin", MockFirebaseAdmin)

    initialize_firebase_admin()


class MockFirebaseAdmin:
    @staticmethod
    def initialize_app(credentials=None):  # sourcery skip: do-not-use-staticmethod
        pass
