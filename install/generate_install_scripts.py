"""
Generate ACM installation SQL scripts from the current database state.

Outputs:
    install/sql/00_create_database.sql
    install/sql/10_tables.sql
    install/sql/20_foreign_keys.sql
    install/sql/30_indexes.sql
    install/sql/40_views.sql
    install/sql/50_procedures.sql

Usage:
    python install/generate_install_scripts.py --ini-section acm
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.sql_client import SQLClient
from core.observability import Console


OUTPUT_DIR = ROOT / "install" / "sql"


def format_data_type(row: Dict) -> str:
    """Format SQL Server data type with length/precision."""
    dtype = row["data_type"].lower()
    length = row.get("char_len")
    precision = row.get("num_precision")
    scale = row.get("num_scale")
    dt_precision = row.get("dt_precision")

    if dtype in {"varchar", "nvarchar", "char", "nchar", "varbinary"}:
        if length is None:
            return dtype
        if length == -1:
            return f"{dtype}(MAX)"
        return f"{dtype}({length})"
    if dtype in {"decimal", "numeric"}:
        if precision is not None and scale is not None:
            return f"{dtype}({precision},{scale})"
    if dtype in {"datetime2", "datetimeoffset", "time"}:
        if dt_precision is not None:
            return f"{dtype}({dt_precision})"
    if dtype == "float" and precision:
        return f"{dtype}({precision})"
    return dtype


def fetch_tables(cur) -> List[str]:
    cur.execute(
        """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA='dbo' AND TABLE_TYPE='BASE TABLE'
        ORDER BY TABLE_NAME
        """
    )
    return [row[0] for row in cur.fetchall()]


def fetch_columns(cur, table: str) -> List[Dict]:
    cur.execute(
        """
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH AS char_len,
            c.NUMERIC_PRECISION AS num_precision,
            c.NUMERIC_SCALE AS num_scale,
            c.DATETIME_PRECISION AS dt_precision,
            c.IS_NULLABLE,
            c.ORDINAL_POSITION,
            CAST(ic.seed_value AS BIGINT) AS seed_value,
            CAST(ic.increment_value AS BIGINT) AS increment_value,
            CASE WHEN ic.column_id IS NULL THEN 0 ELSE 1 END AS is_identity,
            dc.name AS default_name,
            dc.definition AS default_definition
        FROM INFORMATION_SCHEMA.COLUMNS c
        JOIN sys.columns sc
            ON sc.object_id = OBJECT_ID('dbo.' + c.TABLE_NAME)
           AND sc.name = c.COLUMN_NAME
        LEFT JOIN sys.identity_columns ic
            ON ic.object_id = sc.object_id
           AND ic.column_id = sc.column_id
        LEFT JOIN sys.default_constraints dc
            ON dc.parent_object_id = sc.object_id
           AND dc.parent_column_id = sc.column_id
        WHERE c.TABLE_SCHEMA='dbo' AND c.TABLE_NAME = ?
        ORDER BY c.ORDINAL_POSITION
        """,
        (table,),
    )
    cols: List[Dict] = []
    for row in cur.fetchall():
        cols.append(
            {
                "name": row[0],
                "data_type": row[1],
                "char_len": row[2],
                "num_precision": row[3],
                "num_scale": row[4],
                "dt_precision": row[5],
                "nullable": row[6] == "YES",
                "ordinal": row[7],
                "identity_seed": row[8],
                "identity_increment": row[9],
                "is_identity": bool(row[10]),
                "default_name": row[11],
                "default_definition": row[12],
            }
        )
    return cols


def fetch_primary_key(cur, table: str) -> Tuple[str, List[str], str]:
    cur.execute(
        """
        SELECT kc.name, c.name, ic.key_ordinal, idx.type_desc
        FROM sys.key_constraints kc
        JOIN sys.index_columns ic
            ON kc.parent_object_id = ic.object_id
           AND kc.unique_index_id = ic.index_id
        JOIN sys.columns c
            ON ic.object_id = c.object_id
           AND ic.column_id = c.column_id
        JOIN sys.indexes idx
            ON idx.object_id = kc.parent_object_id
           AND idx.index_id = kc.unique_index_id
        WHERE kc.parent_object_id = OBJECT_ID('dbo.' + ?)
          AND kc.type = 'PK'
        ORDER BY ic.key_ordinal
        """,
        (table,),
    )
    rows = cur.fetchall()
    if not rows:
        return "", [], ""
    name = rows[0][0]
    idx_type = rows[0][3]  # CLUSTERED / NONCLUSTERED
    cols = [r[1] for r in rows]
    return name, cols, idx_type


def fetch_unique_constraints(cur) -> Dict[str, List[Dict]]:
    cur.execute(
        """
        SELECT
            t.name AS table_name,
            kc.name AS constraint_name,
            c.name AS column_name,
            ic.key_ordinal,
            idx.type_desc
        FROM sys.key_constraints kc
        JOIN sys.tables t ON t.object_id = kc.parent_object_id
        JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        JOIN sys.indexes idx ON idx.object_id = kc.parent_object_id AND idx.index_id = kc.unique_index_id
        WHERE kc.type = 'UQ' AND t.schema_id = SCHEMA_ID('dbo')
        ORDER BY t.name, kc.name, ic.key_ordinal
        """
    )
    result: Dict[str, List[Dict]] = defaultdict(list)
    for table, constraint, col, ord_pos, idx_type in cur.fetchall():
        result[table].append(
            {
                "constraint": constraint,
                "column": col,
                "ordinal": ord_pos,
                "idx_type": idx_type,
            }
        )
    return result


def fetch_foreign_keys(cur):
    cur.execute(
        """
        SELECT
            fk.name,
            tp.name AS parent_table,
            cp.name AS parent_col,
            tr.name AS ref_table,
            cr.name AS ref_col,
            fkc.constraint_column_id,
            fk.delete_referential_action_desc,
            fk.update_referential_action_desc
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
        JOIN sys.columns cp ON cp.object_id = tp.object_id AND cp.column_id = fkc.parent_column_id
        JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
        JOIN sys.columns cr ON cr.object_id = tr.object_id AND cr.column_id = fkc.referenced_column_id
        WHERE tp.schema_id = SCHEMA_ID('dbo') AND tr.schema_id = SCHEMA_ID('dbo')
        ORDER BY fk.name, fkc.constraint_column_id
        """
    )
    fks: Dict[str, Dict] = {}
    for row in cur.fetchall():
        name, parent, pcol, ref, rcol, ord_pos, delete_action, update_action = row
        if name not in fks:
            fks[name] = {
                "name": name,
                "parent": parent,
                "ref": ref,
                "delete": delete_action,
                "update": update_action,
                "cols": [],
                "ref_cols": [],
            }
        fks[name]["cols"].append(pcol)
        fks[name]["ref_cols"].append(rcol)
    return list(fks.values())


def fetch_indexes(cur) -> Dict[str, List[Dict]]:
    cur.execute(
        """
        SELECT
            t.name AS table_name,
            i.name AS index_name,
            i.is_unique,
            i.type_desc,
            i.filter_definition,
            ic.is_included_column,
            ic.key_ordinal,
            c.name AS column_name,
            ic.index_column_id
        FROM sys.indexes i
        JOIN sys.tables t ON t.object_id = i.object_id
        JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE t.schema_id = SCHEMA_ID('dbo')
          AND i.is_primary_key = 0
          AND i.is_unique_constraint = 0
          AND i.index_id > 0
        ORDER BY t.name, i.name, ic.key_ordinal, ic.index_column_id
        """
    )
    result: Dict[str, List[Dict]] = defaultdict(list)
    for row in cur.fetchall():
        tbl, idx, unique, idx_type, filter_def, is_include, key_ord, col_name, idx_col_id = row
        key_ord = int(key_ord or 0)
        is_include = bool(is_include)
        if not any(item["name"] == idx for item in result[tbl]):
            result[tbl].append(
                {
                    "name": idx,
                    "unique": bool(unique),
                    "type": idx_type,
                    "filter": filter_def,
                    "keys": [],
                    "includes": [],
                }
            )
        target = next(item for item in result[tbl] if item["name"] == idx)
        if is_include:
            target["includes"].append((key_ord, col_name, idx_col_id))
        else:
            target["keys"].append((key_ord, col_name, idx_col_id))
    # Sort columns
    for tbl in result:
        for idx in result[tbl]:
            idx["keys"] = [col for _, col, _ in sorted(idx["keys"], key=lambda x: (x[0], x[2]))]
            idx["includes"] = [col for _, col, _ in sorted(idx["includes"], key=lambda x: (x[0], x[2]))]
    return result


def fetch_modules(cur, object_type: str) -> Dict[str, str]:
    """Fetch definitions for procedures or views."""
    type_map = {"P": "procedure", "V": "view"}
    cur.execute(
        f"""
        SELECT QUOTENAME(OBJECT_SCHEMA_NAME(object_id)) + '.' + QUOTENAME(name) AS full_name,
               OBJECT_DEFINITION(object_id) AS definition
        FROM sys.objects
        WHERE type = ? AND is_ms_shipped = 0
        ORDER BY name
        """,
        (object_type,),
    )
    modules = {}
    for full_name, definition in cur.fetchall():
        if not definition:
            continue
        modules[full_name] = definition
    Console.info(f"Fetched {len(modules)} {type_map.get(object_type, 'modules')}")
    return modules


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    Console.info(f"Wrote {path.relative_to(ROOT)}")


def build_table_script(cur) -> Tuple[str, Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    tables = fetch_tables(cur)
    unique_constraints = fetch_unique_constraints(cur)
    lines: List[str] = ["USE [ACM];", "GO", ""]
    for tbl in tables:
        cols = fetch_columns(cur, tbl)
        pk_name, pk_cols, pk_type = fetch_primary_key(cur, tbl)
        uqs = sorted(unique_constraints.get(tbl, []), key=lambda x: x["ordinal"])

        lines.append(f"-- {tbl}")
        lines.append(f"IF OBJECT_ID('dbo.[{tbl}]','U') IS NULL")
        lines.append("BEGIN")
        lines.append(f"    CREATE TABLE dbo.[{tbl}] (")

        col_lines: List[str] = []
        for col in cols:
            parts = [f"[{col['name']}] {format_data_type(col).upper()}"]
            if col["is_identity"]:
                seed = int(col["identity_seed"] or 1)
                inc = int(col["identity_increment"] or 1)
                parts.append(f"IDENTITY({seed},{inc})")
            parts.append("NULL" if col["nullable"] else "NOT NULL")
            if col["default_definition"]:
                def_name = col["default_name"] or f"DF_{tbl}_{col['name']}"
                parts.append(f"CONSTRAINT [{def_name}] DEFAULT {col['default_definition']}")
            col_lines.append("        " + " ".join(parts))

        if pk_cols:
            pk_cols_formatted = ", ".join(f"[{c}]" for c in pk_cols)
            pk_clause = f"CONSTRAINT [{pk_name}] PRIMARY KEY {pk_type} ({pk_cols_formatted})"
            col_lines.append("        " + pk_clause)

        if col_lines:
            lines.append(",\n".join(col_lines))
        lines.append("    );")
        lines.append("END")
        lines.append("GO\n")

    return "\n".join(lines), unique_constraints, tables


def build_unique_constraints_script(unique_constraints: Dict[str, List[Dict]], tables: List[str]) -> str:
    lines: List[str] = ["USE [ACM];", "GO", ""]
    for tbl in tables:
        constraints = defaultdict(list)
        for uc in unique_constraints.get(tbl, []):
            constraints[uc["constraint"]].append((uc["ordinal"], uc["column"]))
        for cname, cols in constraints.items():
            col_list = ", ".join(f"[{c}]" for _, c in sorted(cols))
            lines.append(f"IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = '{cname}' AND parent_object_id = OBJECT_ID('dbo.[{tbl}]'))")
            lines.append("BEGIN")
            lines.append(f"    ALTER TABLE dbo.[{tbl}] ADD CONSTRAINT [{cname}] UNIQUE ({col_list});")
            lines.append("END")
            lines.append("GO\n")
    return "\n".join(lines)


def build_foreign_key_script(cur) -> str:
    fks = fetch_foreign_keys(cur)
    lines: List[str] = ["USE [ACM];", "GO", ""]
    for fk in sorted(fks, key=lambda x: x["name"]):
        parent_cols = ", ".join(f"[{c}]" for c in fk["cols"])
        ref_cols = ", ".join(f"[{c}]" for c in fk["ref_cols"])
        delete_clause = "" if fk["delete"] == "NO_ACTION" else f" ON DELETE {fk['delete']}"
        update_clause = "" if fk["update"] == "NO_ACTION" else f" ON UPDATE {fk['update']}"
        lines.append(f"IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = '{fk['name']}' AND parent_object_id = OBJECT_ID('dbo.[{fk['parent']}]'))")
        lines.append("BEGIN")
        lines.append(
            f"    ALTER TABLE dbo.[{fk['parent']}] WITH CHECK ADD CONSTRAINT [{fk['name']}] "
            f"FOREIGN KEY ({parent_cols}) REFERENCES dbo.[{fk['ref']}] ({ref_cols}){delete_clause}{update_clause};"
        )
        lines.append(f"    ALTER TABLE dbo.[{fk['parent']}] CHECK CONSTRAINT [{fk['name']}];")
        lines.append("END")
        lines.append("GO\n")
    return "\n".join(lines)


def build_index_script(cur, tables: List[str]) -> str:
    indexes = fetch_indexes(cur)
    lines: List[str] = ["USE [ACM];", "GO", ""]
    for tbl in tables:
        for idx in indexes.get(tbl, []):
            key_cols = ", ".join(f"[{c}]" for c in idx["keys"])
            include_clause = f" INCLUDE ({', '.join(f'[{c}]' for c in idx['includes'])})" if idx["includes"] else ""
            filter_clause = f" WHERE {idx['filter']}" if idx["filter"] else ""
            unique = "UNIQUE " if idx["unique"] else ""
            idx_type = idx["type"]
            lines.append(f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = '{idx['name']}' AND object_id = OBJECT_ID('dbo.[{tbl}]'))")
            lines.append("BEGIN")
            lines.append(
                f"    CREATE {unique}{idx_type} INDEX [{idx['name']}] ON dbo.[{tbl}] ({key_cols}){include_clause}{filter_clause};"
            )
            lines.append("END")
            lines.append("GO\n")
    return "\n".join(lines)


def normalize_create_statement(definition: str, kind: str) -> str:
    """Replace CREATE with CREATE OR ALTER for idempotent scripts."""
    pattern = re.compile(rf"CREATE\s+{kind}\b", re.IGNORECASE)
    return pattern.sub(f"CREATE OR ALTER {kind}", definition, count=1)


def build_module_script(modules: Dict[str, str], kind: str) -> str:
    lines: List[str] = ["USE [ACM];", "GO", ""]
    for name, definition in modules.items():
        normalized = normalize_create_statement(definition, kind)
        lines.append(normalized.strip())
        lines.append("GO\n")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ACM installation SQL scripts from current database.")
    parser.add_argument("--ini-section", default="acm", help="configs/sql_connection.ini section (default: acm)")
    args = parser.parse_args()

    ensure_output_dir()
    sql = SQLClient.from_ini(args.ini_section).connect()
    cur = sql.cursor()

    # 00 - create database stub
    create_db = (
        "IF DB_ID(N'ACM') IS NULL\n"
        "BEGIN\n"
        "    PRINT('Creating ACM database');\n"
        "    CREATE DATABASE [ACM];\n"
        "END\n"
        "GO\n"
        "ALTER DATABASE [ACM] SET RECOVERY SIMPLE;\n"
        "GO\n"
    )
    write_file(OUTPUT_DIR / "00_create_database.sql", create_db)

    table_script, unique_constraints, tables = build_table_script(cur)
    write_file(OUTPUT_DIR / "10_tables.sql", table_script)

    write_file(OUTPUT_DIR / "15_unique_constraints.sql", build_unique_constraints_script(unique_constraints, tables))
    write_file(OUTPUT_DIR / "20_foreign_keys.sql", build_foreign_key_script(cur))
    write_file(OUTPUT_DIR / "30_indexes.sql", build_index_script(cur, tables))

    views = fetch_modules(cur, "V")
    write_file(OUTPUT_DIR / "40_views.sql", build_module_script(views, "VIEW"))

    procs = fetch_modules(cur, "P")
    write_file(OUTPUT_DIR / "50_procedures.sql", build_module_script(procs, "PROCEDURE"))

    sql.close()
    Console.info("Export completed.")


if __name__ == "__main__":
    main()
