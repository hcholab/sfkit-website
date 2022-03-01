from src import initialize_firebase_admin


def test_initialize_firebase_admin(mocker):
    mocker.patch("src.os.path.exists", return_value=False)
    mocker.patch("src.firebase_admin", MockFirebaseAdmin)

    initialize_firebase_admin()


class MockFirebaseAdmin:
    @staticmethod
    def initialize_app(credentials=None):
        pass
