from django.core.cache import cache
from django.utils import timezone
import datetime
import json

PREFIX = "jwt_session:"  # redis key prefix

def _key(session_id: str):
    return PREFIX + str(session_id)

def create_session(session_id: str, user_id: str, refresh_jti: str, expires_at: datetime.datetime, scope: str):
    """
    Store a session record in Redis containing user_id, current refresh_jti and scope.
    TTL = expires_at - now.
    """
    ttl = max(int((expires_at - timezone.now()).total_seconds()), 0)
    if ttl <= 0:
        return False
    value = {"user_id": str(user_id), "refresh_jti": str(refresh_jti), "scope": scope}
    cache.set(_key(session_id), json.dumps(value), timeout=ttl)
    return True

def get_session(session_id: str):
    raw = cache.get(_key(session_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def update_session_jti(session_id: str, new_refresh_jti: str, expires_at: datetime.datetime):
    sess = get_session(session_id)
    if sess is None:
        return False
    sess['refresh_jti'] = str(new_refresh_jti)
    ttl = max(int((expires_at - timezone.now()).total_seconds()), 0)
    cache.set(_key(session_id), json.dumps(sess), timeout=ttl)
    return True

def is_session_active(session_id: str) -> bool:
    return get_session(session_id) is not None

def revoke_session(session_id: str):
    cache.delete(_key(session_id))
