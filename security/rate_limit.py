from time import time
from collections import defaultdict

_BUCKET = defaultdict(list)
LIMIT = 10
WINDOW = 60  # seconds

def is_rate_limited(key: str) -> bool:
    now = time()
    _BUCKET[key] = [t for t in _BUCKET[key] if now - t < WINDOW]

    if len(_BUCKET[key]) >= LIMIT:
        return True

    _BUCKET[key].append(now)
    return False
