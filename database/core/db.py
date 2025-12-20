# database/db.py
import logging
from contextlib import contextmanager
from typing import Any, List, Optional
from database.core.connect import get_connection

LOG = logging.getLogger(__name__)

def run_query(query: str, params: Optional[tuple] = None, fetch: bool = False, many: bool = False, commit: bool = True):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            try:
                if many and params:
                    cur.executemany(query, params)
                elif params is not None:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                rows = cur.fetchall() if fetch else None
                if commit:
                    conn.commit()
                return rows
            except Exception as e:
                conn.rollback()
                LOG.exception("Query failed: %s -- %s -- %s", e, query, params)
                raise
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
    except Exception as e:
        LOG.exception("run_query connection error: %s", e)
        return None

@contextmanager
def transactional():
    conn = None
    try:
        conn_ctx = get_connection()
        conn = conn_ctx.__enter__()
        cur = conn.cursor()
        class TX:
            def execute(self, q, p=None):
                return cur.execute(q, p)
            def fetchall(self):
                return cur.fetchall()
            def fetchone(self):
                return cur.fetchone()
        tx = TX()
        yield tx
        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        LOG.exception("Transaction failed: %s", e)
        raise
    finally:
        try:
            cur.close()
        except Exception:
            pass
        if conn:
            try:
                conn_ctx.__exit__(None, None, None)
            except Exception:
                pass
