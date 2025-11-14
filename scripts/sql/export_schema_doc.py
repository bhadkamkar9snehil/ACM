from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from textwrap import dedent

from core.sql_client import SQLClient


def _fetch_tables(cur) -> list[str]:
    cur.execute(
        dedent(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
            """
        )
    )
    return [row[0] for row in cur.fetchall()]


def _fetch_columns(cur, table: str) -> list[dict]:
    cur.execute(
        dedent(
            """
            SELECT COLUMN_NAME,
                   DATA_TYPE,
                   IS_NULLABLE,
                   COALESCE(CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION) AS LEN_PREC,
                   COLUMN_DEFAULT,
                   ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'dbo'
              AND TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """
        ),
        (table,),
    )
    columns: list[dict] = []
    for name, dtype, nullable, len_prec, default, pos in cur.fetchall():
        columns.append(
            {
                "name": name,
                "data_type": dtype,
                "nullable": nullable == "YES",
                "len_prec": len_prec,
                "default": default,
                "ordinal": pos,
            }
        )
    return columns


def _fetch_primary_keys(cur) -> dict[str, list[str]]:
    cur.execute(
        dedent(
            """
            SELECT KU.TABLE_NAME,
                   KU.COLUMN_NAME,
                   KU.ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS TC
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS KU
              ON TC.CONSTRAINT_NAME = KU.CONSTRAINT_NAME
             AND TC.TABLE_SCHEMA = KU.TABLE_SCHEMA
            WHERE TC.TABLE_SCHEMA = 'dbo'
              AND TC.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY KU.TABLE_NAME, KU.ORDINAL_POSITION
            """
        )
    )
    pk_map: dict[str, list[str]] = defaultdict(list)
    for table, column, _ in cur.fetchall():
        pk_map[table].append(column)
    return pk_map


def _render_markdown(schema: dict[str, list[dict]], pk_map: dict[str, list[str]], generated_at: datetime) -> str:
    header = dedent(
        f"""
        # ACM SQL Schema Reference
        _Generated automatically on {generated_at.strftime('%Y-%m-%d %H:%M:%S')}_

        This document is produced by `python scripts/sql/export_schema_doc.py` and reflects the live structure
        of the `ACM` database. Re-run the script whenever tables change.
        """
    ).strip()

    summary_rows = ["| Table | Column Count | Primary Key |", "| --- | ---: | --- |"]
    for table, columns in schema.items():
        pk = ", ".join(pk_map.get(table, [])) or "—"
        summary_rows.append(f"| dbo.{table} | {len(columns)} | {pk} |")

    body_sections = []
    for table, columns in schema.items():
        pk = ", ".join(pk_map.get(table, [])) or "—"
        section_lines = [
            f"## dbo.{table}",
            f"- **Primary Key:** {pk}",
            "",
            "| Column | Data Type | Nullable | Length/Precision | Default |",
            "| --- | --- | --- | --- | --- |",
        ]
        for col in columns:
            nullable = "YES" if col["nullable"] else "NO"
            len_prec = col["len_prec"] if col["len_prec"] is not None else "—"
            default = col["default"] or "—"
            section_lines.append(
                f"| {col['name']} | {col['data_type']} | {nullable} | {len_prec} | {default} |"
            )
        body_sections.append("\n".join(section_lines))

    return "\n\n".join([header, "\n".join(summary_rows), *body_sections])


def export_schema(ini_section: str, output_path: Path) -> None:
    client = SQLClient.from_ini(ini_section)
    conn = client.connect()
    try:
        cur = conn.cursor()
        tables = _fetch_tables(cur)
        pk_map = _fetch_primary_keys(cur)
        schema: dict[str, list[dict]] = {}
        for table in tables:
            schema[table] = _fetch_columns(cur, table)
    finally:
        conn.close()
    markdown = _render_markdown(schema, pk_map, datetime.now())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ACM SQL schema to Markdown.")
    parser.add_argument(
        "--ini-section",
        default="acm",
        help="Section inside configs/sql_connection.ini to use (default: acm).",
    )
    parser.add_argument(
        "--output",
        default="docs/sql/SQL_SCHEMA_REFERENCE.md",
        help="Destination Markdown file (default: docs/sql/SQL_SCHEMA_REFERENCE.md).",
    )
    args = parser.parse_args()
    export_schema(args.ini_section, Path(args.output))


if __name__ == "__main__":
    main()
