# database/connect.py
import os
import logging
import time
from contextlib import contextmanager
from psycopg2 import pool, OperationalError
import psycopg2.extras
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Tuple
import codecs

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

# ---------- robust dotenv loader (handles utf-16 BOM etc) ----------
def _safe_load_dotenv(path: Path) -> None:
    """
    Attempt to load dotenv from `path`. If reading fails due to encoding,
    try several encodings and rewrite as UTF-8 so python-dotenv can read it.
    """
    if not path.exists():
        return

    try:
        # try normal load first
        load_dotenv(path, override=False)
        return
    except UnicodeDecodeError:
        LOG.warning("dotenv %s not utf-8; attempting fallback encodings", path)

    # Try reading with common encodings and re-save as utf-8
    encodings_to_try = ["utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1", "cp1252"]
    for enc in encodings_to_try:
        try:
            text = path.read_text(encoding=enc)
            # rewrite as utf-8 (atomic-ish)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
            LOG.info("Re-encoded %s from %s -> utf-8", path, enc)
            load_dotenv(path, override=False)
            return
        except Exception:
            continue

    LOG.error("Could not read dotenv %s with fallback encodings; leaving unchanged", path)


_proj_root = Path(__file__).resolve().parents[2]
_env_default = _proj_root / ".env"
_safe_load_dotenv(_env_default)

# ---------- config & defaults ----------
# Pool sizing
DB_MINCONN = int(os.getenv("DB_MINCONN", 1))
DB_MAXCONN = int(os.getenv("DB_MAXCONN", 10))

# Retry behavior for establishing pool
DB_CONN_RETRIES = int(os.getenv("DB_CONN_RETRIES", 4))
DB_CONN_RETRY_DELAY = float(os.getenv("DB_CONN_RETRY_DELAY", 1.5))

# Preferred: full DSN (Supabase supplies this). It should include user/password/host/db.
FULL_DSN = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DSN")

# Individual parts (used only if FULL_DSN missing or invalid)
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
try:
    DB_PORT = int(os.getenv("DATABASE_PORT", 5432))
except Exception:
    LOG.warning("DATABASE_PORT is not an integer; defaulting to 5432")
    DB_PORT = 5432

DB_NAME = os.getenv("DATABASE_DBNAME") or os.getenv("DATABASE_dbname") or "postgres"
DB_USER = os.getenv("DATABASE_USER") or os.getenv("USER") or "postgres"
DB_PASSWORD = os.getenv("DATABASE_PASSWORD") or ""

_pool: Optional[pool.SimpleConnectionPool] = None


def _safe_parse_dsn(dsn: Optional[str]) -> Optional[Tuple[str, int, str, Optional[str], Optional[str]]]:
    """
    Parse DSN and return (host, port, dbname, user, pwd) if valid; otherwise None.
    """
    if not dsn:
        return None
    try:
        p = urlparse(dsn)
        host = p.hostname
        port = p.port
        dbname = p.path.lstrip("/") if p.path else None
        user = p.username
        pwd = p.password
        if not host or not port or not dbname:
            LOG.debug("Invalid DSN: missing host/port/dbname -> host=%r port=%r db=%r", host, port, dbname)
            return None
        return host, int(port), dbname, user, pwd
    except Exception as e:
        LOG.debug("Failed to parse DSN: %s", e)
        return None


def _ensure_ssl_in_dsn(dsn: Optional[str]) -> Optional[str]:
    """
    Ensure the DSN includes sslmode=require for Supabase TLS.
    Returns None if dsn is None.
    """
    if not dsn:
        return None
    if "sslmode=" in dsn:
        return dsn
    if "?" in dsn:
        return dsn + "&sslmode=require"
    return dsn + "?sslmode=require"


def init_pool():
    """
    Initialize a psycopg2 SimpleConnectionPool. Prefer FULL_DSN if provided and valid.
    Retries a few times on transient failure and logs clear reasons on failure.
    """
    global _pool
    if _pool is not None:
        return _pool

    attempts = 0
    last_exc = None

    # Validate DSN before using it
    parsed = _safe_parse_dsn(FULL_DSN) if FULL_DSN else None
    if FULL_DSN and not parsed:
        LOG.warning("SUPABASE_DATABASE_URL appears malformed or missing parts. Falling back to individual DATABASE_* vars.")

    while attempts < DB_CONN_RETRIES:
        try:
            if parsed:
                dsn = _ensure_ssl_in_dsn(FULL_DSN)
                if not dsn:
                    raise RuntimeError("DSN validation failed unexpectedly")
                LOG.info("Creating Postgres pool using FULL_DSN (ssl enforced). Attempt %d", attempts + 1)
                _pool = pool.SimpleConnectionPool(
                    DB_MINCONN,
                    DB_MAXCONN,
                    dsn=dsn,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
            else:
                LOG.info(
                    "Creating Postgres pool using host=%s port=%s db=%s (Attempt %d)",
                    DB_HOST,
                    DB_PORT,
                    DB_NAME,
                    attempts + 1,
                )
                _pool = pool.SimpleConnectionPool(
                    DB_MINCONN,
                    DB_MAXCONN,
                    host=DB_HOST,
                    port=DB_PORT,
                    dbname=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    sslmode="require",
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )

            LOG.info("✅ Postgres connection pool created (min=%s max=%s)", DB_MINCONN, DB_MAXCONN)
            return _pool

        except OperationalError as e:
            last_exc = e
            LOG.warning("Postgres connection attempt %d failed: %s", attempts + 1, e)
            attempts += 1
            time.sleep(DB_CONN_RETRY_DELAY)
        except Exception as e:
            last_exc = e
            LOG.exception("Unexpected error while creating Postgres pool: %s", e)
            attempts += 1
            time.sleep(DB_CONN_RETRY_DELAY)

    LOG.error("❌ Could not create Postgres pool after %d attempts. Last error: %s", DB_CONN_RETRIES, last_exc)
    raise RuntimeError(f"Could not create Postgres pool: {last_exc}")


@contextmanager
def get_connection():
    """
    Acquire a connection from the pool (initializes pool lazily).
    Yields a psycopg2 connection. Caller must use cursor() and commit/rollback appropriately.
    """
    global _pool
    if _pool is None:
        init_pool()

    # reassure static checkers that _pool is not None
    assert _pool is not None, "Postgres pool not initialized"

    conn = None
    try:
        conn = _pool.getconn()
        yield conn
    except OperationalError as e:
        LOG.exception("DB operational error: %s", e)
        raise
    finally:
        if conn is not None:
            try:
                _pool.putconn(conn)
            except Exception:
                LOG.exception("Failed to return connection to pool")


def test_connection() -> bool:
    """
    Helper used by tests to validate DB connectivity.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                _ = cur.fetchone()
                return True
    except Exception as e:
        LOG.error("DB test failed: %s", e)
        return False
