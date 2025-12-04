from __future__ import annotations
from functools import wraps
from typing import Optional
from flask import request, abort
from models.core_models import FeatureFlag
from models import db

class _Flags:
    _cache = None
    def get(self, key: str, default: bool=False) -> bool:
        if self._cache is None:
            self._cache = {f.key: f.enabled for f in db.session.query(FeatureFlag).all()}
        return self._cache.get(key, default)
    def invalidate_cache(self):
        self._cache = None

flags = _Flags()

def require_flag(key: str, default: bool=False):
    def deco(fn):
        @wraps(fn)
        def inner(*a, **kw):
            if not flags.get(key, default):
                abort(403, f"Feature '{key}' disabled")
            return fn(*a, **kw)
        return inner
    return deco

def require_flag_admin(fn):
    @wraps(fn)
    def inner(*a, **kw):
        # Replace with real auth/roles. For now, allow if header present
        if request.headers.get("X-Mina-Admin") != "1":
            abort(403, "Admin required")
        return fn(*a, **kw)
    return inner