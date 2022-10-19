import google.auth.transport.requests
from flask import Blueprint, current_app, request
from google.oauth2 import id_token
from werkzeug import Request, Response

bp = Blueprint("api", __name__)


@bp.route("/get_doc_ref_dict", methods=["GET"])
def get_doc_ref_dict() -> Response:
    if not verify_authorization_header(request):
        return Response({"error": "unauthorized"}, 401)

    study_title: str = str(request.args.get("study_title"))
    return Response(current_app.config["DATABASE"].collection("studies").document(study_title).get().to_dict() or {})


@bp.route("/get_study_options", methods=["GET"])
def get_study_options() -> Response:
    token: dict = verify_authorization_header(request, authenticate_user=False)
    if not token:
        return Response({"error": "unauthorized"}, 401)

    options: list = []
    sa_email: str = str(token.get("email"))
    for doc_ref in current_app.config["DATABASE"].collection("studies").stream():
        doc_ref_dict: dict = doc_ref.to_dict() or {}
        options.extend(
            (doc_ref.id, user)
            for user in doc_ref_dict["participants"]
            if doc_ref_dict["personal_parameters"][user]["SA_EMAIL"]["value"] == sa_email
        )
    return Response({"options": options})


@bp.route("/update_firestore", methods=["GET"])
def update_firestore() -> Response:
    if not verify_authorization_header(request):
        return Response({"error": "unauthorized"}, 401)

    msg: str = str(request.args.get("msg"))
    _, parameter, title, email = msg.split("::")
    doc_ref = current_app.config["DATABASE"].collection("studies").document(title.replace(" ", "").lower())
    doc_ref_dict: dict = doc_ref.get().to_dict()

    if parameter.startswith("status"):
        status = parameter.split("=")[1]
        doc_ref_dict["status"][email] = [status]
    else:
        name, value = parameter.split("=")
        if name in doc_ref_dict["personal_parameters"][email]:
            doc_ref_dict["personal_parameters"][email][name]["value"] = value
        elif name in doc_ref_dict["parameters"]:
            doc_ref_dict["parameters"][name]["value"] = value
        else:
            print(f"parameter {name} not found in {title}")
            return Response({"error": f"parameter {name} not found in {title}"}, 400)
    doc_ref.set(doc_ref_dict)

    return Response("", status=200)


def verify_authorization_header(request: Request, authenticate_user: bool = True) -> dict:
    print("verifying authorization token")

    study_title = request.args.get("study_title")
    user = request.args.get("user")

    token = request.headers.get("Authorization")
    if not token:
        print("No token provided")
        return {}
    try:
        token = token.split(" ")[1]
        token_payload = verify_token(token)
    except Exception as e:
        print(e)
        return {}

    if authenticate_user:
        # authenticate user by project or service account
        if "broad-cho-priv" in token_payload["google"]["compute_engine"]["project_id"]:
            return token_payload
        doc_ref = current_app.config["DATABASE"].collection("studies").document(study_title)
        doc_ref_dict: dict = doc_ref.get().to_dict()
        if doc_ref_dict["personal_parameters"][user]["SA_EMAIL"]["value"] == token_payload["email"]:
            return token_payload
        return {}

    return token_payload


def verify_token(token: str) -> dict:
    """Verify token signature and return the token payload"""
    request = google.auth.transport.requests.Request()
    return id_token.verify_token(token, request=request)
