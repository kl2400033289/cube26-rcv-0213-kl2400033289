import sqlite3
import json
from pathlib import Path


DB_PATH = Path("receiving.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS receiving_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT UNIQUE,
            unit_id TEXT,
            org_id TEXT,
            operator_id TEXT,
            captured_at TEXT,

            po_number TEXT,
            po_line INTEGER,
            sku TEXT,
            product_title TEXT,

            cartons_ordered INTEGER,
            units_per_carton_ordered INTEGER,
            qty_ordered INTEGER,

            result_json TEXT,
            overall_verdict TEXT,

            photo_count INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_receiving_record(record):
    expected = record.get("expected", {})
    result = record.get("result", {})

    conn = get_connection()

    conn.execute("""
        INSERT OR REPLACE INTO receiving_records (
            record_id,
            unit_id,
            org_id,
            operator_id,
            captured_at,
            po_number,
            po_line,
            sku,
            product_title,
            cartons_ordered,
            units_per_carton_ordered,
            qty_ordered,
            result_json,
            overall_verdict,
            photo_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("record_id"),
        record.get("unit_id"),
        record.get("org_id"),
        record.get("operator_id"),
        record.get("captured_at"),

        expected.get("po_number"),
        expected.get("po_line"),
        expected.get("sku"),
        expected.get("product_title"),

        expected.get("cartons_ordered"),
        expected.get("units_per_carton_ordered"),
        expected.get("qty_ordered"),

        json.dumps(result),
        result.get("overall_verdict"),

        record.get("photo_count", 0)
    ))

    conn.commit()
    conn.close()


def get_receiving_records():
    conn = get_connection()

    rows = conn.execute("""
        SELECT *
        FROM receiving_records
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]
