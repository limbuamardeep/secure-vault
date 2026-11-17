import os

from cryptography.exceptions import InvalidTag
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..crypto import decrypt, derive_kek, encrypt, new_recovery_key, parse_recover_key
from ..extensions import db
from ..keycache import key_cache
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
    salt = os.urandom(16)
    data_key = os.urandom(32)
    kek = derive_kek(data["password"], salt)
    recovery_raw, recovery_text = new_recovery_key()
    user = User(
        first_name=data["first_name"].strip(),
        last_name=data["last_name"].strip(),
        email=data["email"].strip().lower(),
        password_hash=generate_password_hash(data["password"]),
        kdf_salt=salt,
        wrapped_key=encrypt(kek, data_key),
        recovery_wrapped_key=encrypt(recovery_raw, data_key),
        role="user",
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="Email already registered"), 409
    return jsonify(id=user.id, email=user.email, recovery_key=recovery_text), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = db.session.execute(
        db.select(User).filter_by(email=email)
    ).scalar_one_or_none()

    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify(error="Invalid email or password"), 401
    kek = derive_kek(password, user.kdf_salt)
    data_key = decrypt(kek, user.wrapped_key)
    token = create_access_token(identity=str(user.id))
    key_cache[decode_token(token)["jti"]] = data_key
    return jsonify(access_token=token)


@bp.get("/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        return jsonify(error="User not found"), 404
    return jsonify(id=user.id, email=user.email, first_name=user.first_name)


@bp.post("/logout")
@jwt_required()
def logout():
    key_cache.pop(get_jwt()["jti"], None)
    return "", 204


@bp.post("/recover")
def recover():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    new_pw = data.get("new_password") or ""
    if len(new_pw) < 8:
        return jsonify(error="Password must be atleast 8 characters"), 400
    user = db.session.execute(
        db.select(User).filter_by(email=email)
    ).scalar_one_or_none()

    try:
        if user is None:
            raise ValueError
        data_key = decrypt(
            parse_recover_key(data.get("recovery_key", "")), user.recovery_wrapped_key
        )
    except (InvalidTag, ValueError):
        return jsonify(error="Invalid email or password"), 400
    salt = os.urandom(16)
    user.kdf_salt = salt
    user.wrapped_key = encrypt(derive_kek(new_pw, salt), data_key)
    user.password_hash = generate_password_hash(new_pw)
    db.session.commit()
    return jsonify(message="Master password reset successfully"), 200


@bp.post("/change-password")
@jwt_required()
def change_password():
    data = request.get_json(silent=True) or {}
    old_pw = data.get("old_password") or ""
    new_pw = data.get("new_password") or ""
    if len(new_pw) < 8:
        return jsonify(error="Password must be atleast 8 characters"), 400
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None or not check_password_hash(user.password_hash, old_pw):
        return jsonify(error="Password do not match"), 400
    data_key = decrypt(derive_kek(old_pw, user.kdf_salt), user.wrapped_key)
    salt = os.urandom(16)
    user.kdf_salt = salt
    user.wrapped_key = encrypt(derive_kek(new_pw, salt=salt), data_key)
    user.password_hash = generate_password_hash(new_pw)
    db.session.commit()
    key_cache[get_jwt()["jti"]] = data_key
    return jsonify("Password Changed!"), 200
