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
            record_id TEXT PRIMARY KEY,
            unit_id TEXT NOT NULL,
            org_id TEXT,
            operator_id TEXT,
            captured_at TEXT,

            po_number TEXT,
            po_line INTEGER,
            sku TEXT,
            product_title TEXT,

            cartons_ordered INTEGER,
            cartons_received INTEGER,
            units_per_carton_ordered INTEGER,
            units_per_carton_counted INTEGER,
            qty_ordered INTEGER,
            qty_received INTEGER,

            identity_verdict TEXT,
            identity_evidence TEXT,

            quantity_verdict TEXT,
            quantity_evidence TEXT,

            carton_damage_verdict TEXT,
            carton_damage_evidence TEXT,

            unit_damage_verdict TEXT,
            unit_damage_evidence TEXT,

            quality_verdict TEXT,
            quality_evidence TEXT,

            overall_verdict TEXT,
            summary TEXT,

            model TEXT,
            photo_count INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_receiving_record(
    record_id,
    receiving_data,
    result,
    photo_count=0
):
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
            cartons_received,
            units_per_carton_ordered,
            units_per_carton_counted,
            qty_ordered,
            qty_received,

            identity_verdict,
            identity_evidence,

            quantity_verdict,
            quantity_evidence,

            carton_damage_verdict,
            carton_damage_evidence,

            unit_damage_verdict,
            unit_damage_evidence,

            quality_verdict,
            quality_evidence,

            overall_verdict,
            summary,

            model,
            photo_count
        )
        VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?
        )
    """, (
        record_id,
        receiving_data.get("unit_id"),
        receiving_data.get("org_id"),
        receiving_data.get("operator_id"),
        receiving_data.get("captured_at"),

        receiving_data.get("po_number"),
        receiving_data.get("po_line"),
        receiving_data.get("sku"),
        receiving_data.get("product_title"),

        receiving_data.get("cartons_ordered"),
        result.get("cartons_received"),
        receiving_data.get("units_per_carton_ordered"),
        result.get("units_per_carton_counted"),
        receiving_data.get("qty_ordered"),
        result.get("qty_received"),

        result.get("identity", {}).get("verdict"),
        result.get("identity", {}).get("evidence"),

        result.get("quantity", {}).get("verdict"),
        result.get("quantity", {}).get("evidence"),

        result.get("carton_damage", {}).get("verdict"),
        result.get("carton_damage", {}).get("evidence"),

        result.get("unit_damage", {}).get("verdict"),
        result.get("unit_damage", {}).get("evidence"),

        result.get("quality", {}).get("verdict"),
        result.get("quality", {}).get("evidence"),

        result.get("overall_verdict"),
        result.get("summary"),

        result.get("model"),
        photo_count
    ))

    conn.commit()
    conn.close()


def get_record(record_id):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT * FROM receiving_records
        WHERE record_id = ?
        """,
        (record_id,)
    ).fetchone()

    conn.close()

    if row:
        return dict(row)

    return None


def get_records_by_unit(unit_id):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT * FROM receiving_records
        WHERE unit_id = ?
        ORDER BY created_at DESC
        """,
        (unit_id,)
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]
