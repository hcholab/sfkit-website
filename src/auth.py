import functools
from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app,
)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        db = current_app.config["DATABASE"]

        email = request.form["email"]
        password = request.form["password"]
        password_check = request.form["password_check"]

        if not email:
            flash("Email is required.")
        elif not password:
            flash("Password is required.")
        elif password_check != password:
            flash("Passwords do not match. Please double-check and try again.")
        elif db.collection("users").document(email).get().exists:
            flash("Email already taken.")
        else:
            doc_ref = db.collection("users").document(email)
            doc_ref.set(
                {
                    "email": email,
                    "password": generate_password_hash(password),
                    "gcp_project": "",
                }
            )
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        db = current_app.config["DATABASE"]

        email = request.form["email"]
        password = request.form["password"]

        user = db.collection("users").document(email).get()
        user_dict = user.to_dict()

        if not user_dict:
            flash("Incorrect email.")
        elif not check_password_hash(user_dict["password"], password):
            flash("Incorrect password.")
        else:
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("gwas.index"))

    return render_template("auth/login.html")


@bp.route("/<id>/user", methods=("GET", "POST"))
@login_required
def user(id):
    db = current_app.config["DATABASE"]

    user = db.collection("users").document(id).get().to_dict()
    if request.method == "POST":
        doc_ref = db.collection("users").document(id)
        doc_ref.set({"gcp_project": request.form["gcp_project"]}, merge=True)
        return redirect(url_for("gwas.index"))
    return render_template("auth/user.html", user=user)


@bp.before_app_request
def load_logged_in_user():
    db = current_app.config["DATABASE"]

    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = db.collection("users").document(user_id).get().to_dict()
        g.user["id"] = user_id


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
