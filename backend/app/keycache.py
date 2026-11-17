from cachetools import TTLCache
from flask_jwt_extended import get_jwt

key_cache = TTLCache(maxsize=1024, ttl=900)


def current_data_Key() -> bytes | None:
    return key_cache.get(get_jwt()["jti"])
