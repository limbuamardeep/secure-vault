# Secure Vault

A password-manager backend built with Flask. Users can register, log in with JWT authentication, and protect their vault data with a per-user encryption key.

> **Status:** Authentication, password recovery, password changes, per-user key wrapping, and JWT-protected password-entry CRUD are implemented.

## Features implemented so far

- Application factory (`create_app`) with environment-based configuration
- User model with a unique email constraint
- Password-entry model with a one-to-many relationship to users (cascade delete)
- Signup, login, current-user and logout endpoints
- Password change and recovery-key password reset endpoints
- Password hashing with Werkzeug
- JWT access tokens (15-minute expiry) via Flask-JWT-Extended
- AES-GCM encryption with a per-user data key
- Scrypt key derivation from the master password
- Recovery-key wrapping of the per-user data key
- Password-entry listing, creation, reveal, editing, and deletion
- AES-GCM encryption for stored password values
- Entries scoped to the authenticated user's JWT identity
- Database migrations with Flask-Migrate / Alembic
- Health-check endpoint
- Pytest coverage for cryptography and authentication/recovery flows

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
    │   ├── crypto.py          # Key derivation, AES-GCM, and recovery keys
    │   └── keycache.py        # Short-lived session data-key cache
    │   └── routes/
    │           ├── auth.py        # /auth blueprint
    │           └── vault.py       # JWT-protected /vault blueprint
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

> `JWT_SECRET_KEY` is required for token signing. Set it separately from `SECRET_KEY`.

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
Register a new user. The email is normalized to lowercase. The response includes a recovery key; store it securely because it is required to reset the master password.

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
| 201 | Created. Returns `{ "id", "email", "recovery_key" }` |
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

### `POST /auth/logout`
Requires the header `Authorization: Bearer <access_token>`. Removes the token's cached data key.

| Status | Meaning |
|--------|---------|
| 204 | Logged out |
| 401 | Missing, invalid or expired token |

### `POST /auth/change-password`
Requires authentication. Re-encrypts the existing per-user data key with a key derived from the new password.

Request:
```json
{
  "old_password": "current-password",
  "new_password": "new-password"
}
```

| Status | Meaning |
|--------|---------|
| 200 | Password changed |
| 400 | New password is too short or the old password is incorrect |
| 401 | Missing, invalid or expired token |

### `POST /auth/recover`
Resets the master password using the recovery key returned by signup. The recovery key is accepted case-insensitively and with spaces or hyphens.

Request:
```json
{
  "email": "ada@example.com",
  "recovery_key": "recovery-key-from-signup",
  "new_password": "new-password"
}
```

| Status | Meaning |
|--------|---------|
| 200 | Password reset |
| 400 | Invalid email/recovery key or new password is too short |

### `GET /vault`
Requires authentication. Returns password entries owned by the authenticated user, ordered by newest first.

| Status | Meaning |
|--------|---------|
| 200 | Returns the user's entries |
| 401 | Missing, invalid or expired token |

### `POST /vault`
Requires authentication. Creates an encrypted password entry.

Request:
```json
{
  "title": "Example Account",
  "username": "ada",
  "password": "entry-secret",
  "url": "https://example.com",
  "category": "Security"
}
```

`category` may be `Email`, `Development`, `Entertainment`, `Finance`, `Security`, `System`, or `Other`. It defaults to `Other`.

| Status | Meaning |
|--------|---------|
| 200 | Returns the created entry metadata |
| 400 | Missing fields or invalid category |
| 401 | Missing, invalid or expired token, or no cached data key |
| 409 | The user already has an entry for that URL |

### `POST /vault/<entry_id>/reveal`
Requires authentication. Decrypts and returns the password for an entry owned by the user.

| Status | Meaning |
|--------|---------|
| 200 | Returns `{ "password": "<plaintext>" }` |
| 401 | Missing, invalid or expired token |
| 409 | Session data key is unavailable or the entry is not owned/found |
| 500 | The encrypted password could not be decrypted |

### `POST /vault/<entry_id>`
Requires authentication. Updates entry fields and/or re-encrypts a new password.

Request fields are optional:
```json
{
  "title": "Updated title",
  "username": "new-username",
  "url": "https://updated.example.com",
  "category": "Development",
  "favorite": true,
  "password": "new-entry-secret"
}
```

| Status | Meaning |
|--------|---------|
| 200 | Returns the updated entry metadata |
| 400 | Invalid category |
| 404 | Entry not found or not owned by the user |
| 409 | Session data key unavailable or URL conflicts with another entry |

### `DELETE /vault/<entry_id>`
Requires authentication. Deletes an entry owned by the user.

| Status | Meaning |
|--------|---------|
| 204 | Entry deleted |
| 400 | Entry not found or not owned by the user |
| 401 | Missing, invalid or expired token |

### Example

```bash
curl -X POST localhost:5000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Ada","last_name":"Lovelace","email":"ada@example.com","password":"supersecret1"}'

TOKEN=$(curl -s -X POST localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ada@example.com","password":"supersecret1"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl localhost:5000/auth/me -H "Authorization: Bearer $TOKEN"

curl -X POST localhost:5000/vault \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Example","username":"ada","password":"entry-secret","url":"https://example.com","category":"Security"}'

curl localhost:5000/vault -H "Authorization: Bearer $TOKEN"
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
| kdf_salt | LargeBinary(16) | Per-user Scrypt salt |
| wrapped_key | LargeBinary | AES-GCM-wrapped per-user data key |
| recovery_wrapped_key | LargeBinary | Recovery-key-wrapped per-user data key |
| created_at | DateTime | UTC |

**password_entries**

| Column | Type | Notes |
|--------|------|-------|
| id | Integer | Primary key |
| user_id | Integer | FK to `users.id`, indexed |
| title, username | String(100) | Required |
| password_enc | LargeBinary | AES-GCM-encrypted password data |
| url | String(255) | Required. Unique per user (`uq_user_url`) |
| category | String(50) | Defaults to `Other` |
| favorite | Boolean | Defaults to `False` |
| created_at | DateTime | UTC |

## Roadmap

- [x] CRUD endpoints for password entries (JWT-protected, scoped to the owner)
- [x] Use the per-user data key to encrypt and decrypt `password_enc`
- [ ] Role-based access control
- [ ] Frontend
