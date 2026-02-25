"""In-memory user store for PoC. Passwords are hashed with PBKDF2-SHA256 (no native deps)."""

from passlib.context import CryptContext

# Use pbkdf2_sha256 so hashing works in any environment (Docker, Alpine, etc.) without bcrypt native build.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# username -> {"username": str, "hashed_password": str}
_users: dict[str, dict] = {}

DEFAULT_SEED_USERNAME = "user@example.com"
DEFAULT_SEED_PASSWORD = "user@123"


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_user_by_username(username: str) -> dict | None:
    """Return user dict (username, hashed_password) or None."""
    return _users.get(username)


def seed_user(username: str = DEFAULT_SEED_USERNAME, password: str = DEFAULT_SEED_PASSWORD) -> None:
    """Seed exactly one user. Idempotent: overwrites if username exists."""
    _users[username] = {
        "username": username,
        "hashed_password": _hash_password(password),
    }


def seed_on_startup() -> None:
    """Ensure the default PoC user exists when the app starts."""
    seed_user()
