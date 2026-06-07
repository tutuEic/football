# -*- coding: utf-8 -*-
"""MySQL connection management with per-database connection pooling."""
import threading
import mysql.connector
from mysql.connector import pooling
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASS

# One pool per database so connections always have the right db selected.
_pools: dict[str, pooling.MySQLConnectionPool] = {}
_pool_lock = threading.Lock()


def _get_pool(db: str) -> pooling.MySQLConnectionPool:
    """Get or create connection pool (thread-safe)."""
    if db not in _pools:
        with _pool_lock:
            # Double-check after acquiring lock
            if db not in _pools:
                _pools[db] = pooling.MySQLConnectionPool(
                    pool_name=f"fb_pool_{db}",
                    pool_size=5,
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASS,
                    database=db,
                    charset="utf8mb4",
                )
    return _pools[db]


def query(sql, params=None, db="football_odds"):
    """Execute a query, return list[dict]."""
    conn = _get_pool(db).get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def execute(sql, params=None, db="football_pred"):
    """Execute a write operation, return lastrowid."""
    conn = _get_pool(db).get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        last_id = cursor.lastrowid
        cursor.close()
        return last_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_connection(db="football_pred"):
    """Get a pooled connection for manual transaction management."""
    return _get_pool(db).get_connection()
