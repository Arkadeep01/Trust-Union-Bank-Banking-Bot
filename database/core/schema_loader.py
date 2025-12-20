# database/schema_loader.py
import os
import logging
from database.core.connect import get_connection

LOG = logging.getLogger(__name__)

def load_sql_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def apply_sql(sql: str):
    stmts = [s.strip() for s in sql.split(";") if s.strip()]
    with get_connection() as conn:
        cur = conn.cursor()
        created, skipped = [], []
        for stmt in stmts:
            try:
                cur.execute(stmt)
            except Exception as e:
                LOG.debug("Stmt failed/ignored: %s -> %s", e, stmt[:80])
        conn.commit()
        cur.close()

def run_all(schema_path="database/data/schema.sql", indexes_path="database/data/schema_indexes.sql", migrations_path="database/data/schema_migrations.sql"):
    LOG.info("Applying main schema...")
    apply_sql(load_sql_file(schema_path))
    LOG.info("Applying indexes...")
    apply_sql(load_sql_file(indexes_path))
    if os.path.exists(migrations_path):
        LOG.info("Applying migrations...")
        apply_sql(load_sql_file(migrations_path))
    LOG.info("Schema apply completed.")
