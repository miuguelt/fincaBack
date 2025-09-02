from datetime import datetime, timezone

def get_utc_now():
    """Solo para JWT - devuelve UTC"""
    return datetime.now(timezone.utc)