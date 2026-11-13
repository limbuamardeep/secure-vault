from datetime import datetime, timezone

from .extensions import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    entries = db.relationship(
        "PasswordEntry", back_populates="owner", cascade="all, delete-orphan"
    )


class PasswordEntry(db.Model):
    __tablename__ = "password_entries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    title = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    password_enc = db.Column(db.LargeBinary, nullable=False)
    url = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), default="Other")
    favorite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    owner = db.relationship("User", back_populates="entries")
    __table_args__ = (db.UniqueConstraint("user_id", "url", name="uq_user_url"),)
