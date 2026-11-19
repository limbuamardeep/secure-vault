from cryptography.exceptions import InvalidTag
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from ..crypto import decrypt, encrypt
from ..extensions import db
from ..keycache import current_data_Key
from ..models import PasswordEntry

bp = Blueprint("vault", __name__, url_prefix="/vault")

CATEGORIES = {
    "Email",
    "Development",
    "Entertainment",
    "Finance",
    "Security",
    "System",
    "Other",
}


def entry_to_dict(e: PasswordEntry) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "username": e.username,
        "url": e.url,
        "category": e.category,
        "favorite": e.favorite,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def get_owned_entry(entry_id: int):
    return db.session.execute(
        db.select(PasswordEntry).filter_by(id=entry_id, user_id=int(get_jwt_identity()))
    ).scalar_one_or_none()


@bp.get("")
@jwt_required()
def list_entries():
    rows = (
        db.session.execute(
            db.select(PasswordEntry)
            .filter_by(user_id=int(get_jwt_identity()))
            .order_by(PasswordEntry.created_at.desc())
        )
        .scalars()
        .all()
    )
    return jsonify([entry_to_dict(e) for e in rows])


@bp.post("")
@jwt_required()
def add_entry():
    key = current_data_Key()
    if key is None:
        return jsonify(error="Session expired, please login again"), 401
    data = request.get_json(silent=True) or {}
    required = ["title", "username", "password", "url"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify(error=f"Missing: {",".join(missing)}"), 400
    category = data.get("category", "Other")
    if category not in CATEGORIES:
        return jsonify(error="Invalid category"), 400
    entry = PasswordEntry(
        user_id=int(get_jwt_identity()),
        title=data["title"].strip(),
        username=data["username"].strip(),
        url=data["url"].strip(),
        category=category,
        password_enc=encrypt(key, data["password"].encode()),
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except IntegrityError:
        return jsonify(error="You already saved entry for this URL"), 409
    return jsonify(entry_to_dict(entry)), 200


@bp.post("/<int:entry_id>/reveal")
@jwt_required()
def reveal(entry_id):
    key = current_data_Key()
    if key is None:
        return jsonify(error="Session expired, please log in again"), 409
    entry = get_owned_entry(entry_id)
    if entry is None:
        return jsonify(error="Not found"), 409
    try:
        password = decrypt(key, entry.password_enc).decode()
    except InvalidTag:
        return jsonify(error="Entry could not be decrypted (data may be corrupted)"), 500
    return jsonify(password=password)


@bp.post("/<int:entry_id>")
@jwt_required()
def edit_entry(entry_id):
    entry = get_owned_entry(entry_id)
    if entry is None:
        return jsonify(error="Not found"), 404
    data = request.get_json(silent=True) or {}
    if "category" in data and data["category"] not in CATEGORIES:
        return jsonify(error="Invalid category"), 400
    for field in ("title", "username", "url", "category", "favorite"):
        if field in data:
            setattr(entry, field, data[field])
    if data.get("password"):
        key = current_data_Key()
        if key is None:
            return jsonify(error="Session expired, please log in again"), 409
        entry.password_enc = encrypt(key, data["password"].encode())
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="You already saved an entry for this URL"), 409
    return jsonify(entry_to_dict(entry))


@bp.delete("/<int:entry_id>")
@jwt_required()
def delete_entry(entry_id):
    entry = get_owned_entry(entry_id)
    if entry is None:
        return jsonify(error="Not found"), 400
    db.session.delete(entry)
    db.session.commit()
    return "", 204
