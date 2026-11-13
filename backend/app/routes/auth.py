from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}
    required = ["first_name", "last_name", "email", "password"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify(error=f"Missing:{','.join(missing)}"), 400
    if len(data["password"]) < 8:
        return jsonify(error="Password must be atleast 8 characters long"), 400
    user = User(
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        email=data["email"].strip(),
        password_hash=generate_password_hash(data["password"]),
        role="user",
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="Email already registered"), 409
    return jsonify(id=user.id, email=user.email), 201
