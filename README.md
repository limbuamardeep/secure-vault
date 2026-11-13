# Secure Vault

A password-manager backend built with Flask. Users can register, log in with JWT authentication, and (in upcoming work) store encrypted credentials in a personal vault.

> **Status:** Work in progress. Authentication is implemented. The password-entry data model exists, but its CRUD endpoints and encryption logic are not built yet.

## Features implemented so far

- Application factory (`create_app`) with environment-based configuration
- User model with a unique email constraint
- Password-entry model with a one-to-many relationship to users (cascade delete)
- Signup, login and current-user endpoints
- Password hashing with Werkzeug
- JWT access tokens (15-minute expiry) via Flask-JWT-Extended
- Database migrations with Flask-Migrate / Alembic
- Health-check endpoint

## Tech stack

| Area | Library |
|------|---------|
| Web framework | Flask 3.1 |
| ORM | Flask-SQLAlchemy / SQLAlchemy 2.1 |
| Migrations | Flask-Migrate (Alembic) |
| Auth | Flask-JWT-Extended |
| Database | SQLite by default, PostgreSQL supported through `psycopg` |
| Config | python-dotenv |

## Project structure

```
secure-vault/
├── requirements.txt
└── backend/
    ├── config.py              # Config class, reads environment variables
    ├── .env.example           # Template for required env vars
    ├── .flaskenv              # FLASK_APP / FLASK_DEBUG
    ├── app/
    │   ├── __init__.py        # App factory, health route
    │   ├── extensions.py      # db, migrate, jwt instances
    │   ├── models.py          # User, PasswordEntry
    │   └── routes/
    │       └── auth.py        # /auth blueprint
    └── migrations/            # Alembic migration history
```

## Getting started

### Prerequisites

- Python 3.11+
- (Optional) PostgreSQL, if you don't want to use SQLite

### Setup

```bash
# from the repository root
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd backend
cp .env.example .env
```

Edit `backend/.env`:

```env
SECRET_KEY=<a-long-random-string>
JWT_SECRET_KEY=<another-long-random-string>
# Optional. Defaults to sqlite:///vault.db
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/secure_vault
```

> `.env.example` currently lists only `SECRET_KEY`. `JWT_SECRET_KEY` is also required for token signing, so make sure you set it.

Generate secure values with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Run migrations

```bash
cd backend
flask db upgrade
```

### Start the server

```bash
cd backend
flask run
```

The API is served at `http://127.0.0.1:5000`.

## API reference

### `GET /`
Health check.

```json
{ "status": "ok" }
```

### `POST /auth/signup`
Register a new user. The email is normalized to lowercase.

Request:
```json
{
  "first_name": "Ada",
  "last_name": "Lovelace",
  "email": "ada@example.com",
  "password": "at-least-8-chars"
}
```

| Status | Meaning |
|--------|---------|
| 201 | Created. Returns `{ "id", "email" }` |
| 400 | Missing fields, or password shorter than 8 characters |
| 409 | Email already registered |

### `POST /auth/login`
Request:
```json
{ "email": "ada@example.com", "password": "at-least-8-chars" }
```

| Status | Meaning |
|--------|---------|
| 200 | Returns `{ "access_token": "<jwt>" }` |
| 401 | Invalid email or password |

### `GET /auth/me`
Requires the header `Authorization: Bearer <access_token>`.

| Status | Meaning |
|--------|---------|
| 200 | Returns `{ "id", "email", "first_name" }` |
| 401 | Missing, invalid or expired token |
| 404 | User no longer exists |

### Example

```bash
curl -X POST localhost:5000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Ada","last_name":"Lovelace","email":"ada@example.com","password":"supersecret1"}'

TOKEN=$(curl -s -X POST localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ada@example.com","password":"supersecret1"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl localhost:5000/auth/me -H "Authorization: Bearer $TOKEN"
```

## Data model

**users**

| Column | Type | Notes |
|--------|------|-------|
| id | Integer | Primary key |
| first_name, last_name | String(80) | Required |
| email | String(120) | Unique, required |
| password_hash | String(256) | Werkzeug hash |
| role | String(20) | Defaults to `user` on signup |
| created_at | DateTime | UTC |

**password_entries**

| Column | Type | Notes |
|--------|------|-------|
| id | Integer | Primary key |
| user_id | Integer | FK to `users.id`, indexed |
| title, username | String(100) | Required |
| password_enc | LargeBinary | Encrypted password (encryption not yet implemented) |
| url | String(255) | Required. Unique per user (`uq_user_url`) |
| category | String(50) | Defaults to `Other` |
| favorite | Boolean | Defaults to `False` |
| created_at | DateTime | UTC |

## Roadmap

- [ ] CRUD endpoints for password entries (JWT-protected, scoped to the owner)
- [ ] Encrypt and decrypt `password_enc` (for example with `cryptography` / Fernet)
- [ ] Role-based access control
- [ ] Tests
- [ ] Frontend
