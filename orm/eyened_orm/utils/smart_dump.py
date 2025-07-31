import mysql.connector
from collections import defaultdict
from eyened_orm.utils.config import DatabaseSettings
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Any


class SQLStatements:
    PK = """
    SELECT TABLE_NAME, COLUMN_NAME
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = %s AND CONSTRAINT_NAME = 'PRIMARY'
    """

    FK = """
    SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
    """

    COLUMN_TYPES = """
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = %s
    """


@dataclass
class ForeignKey:
    ref_table: str
    column: str
    ref_column: str


def format_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return f"'{str(value)}'"


def build_where_clause(condition):
    if isinstance(condition, str):
        return condition
    if isinstance(condition, dict):
        return " AND ".join(
            f"{column} = {format_value(value)}" for column, value in condition.items()
        )
    raise ValueError(f"Unsupported condition type: {type(condition)}")


def is_binary(column_type):
    return column_type.lower() in (
        "binary",
        "varbinary",
        "tinyblob",
        "blob",
        "mediumblob",
        "longblob",
    )


def dump_row(row, columns, table, column_types):
    # skipping NULL values
    # assuming NULL is the default value for all columns
    non_null_columns = [
        (col, column_types[(table, col)]) for col in columns if row[col] is not None
    ]

    placeholders = [
        "_binary %s" if is_binary(column_type) else "%s"
        for _, column_type in non_null_columns
    ]
    value_columns = [
        bytes(row[col]) if is_binary(column_type) else row[col]
        for col, column_type in non_null_columns
    ]
    column_names = [f"`{col}`" for col, _ in non_null_columns]
    return (
        f"INSERT IGNORE INTO `{table}` ({','.join(column_names)}) VALUES ({','.join(placeholders)});",
        tuple(value_columns),
    )


class DatabaseDumper:
    def __init__(
        self,
        config: DatabaseSettings,
        paths: Dict[str, Set[str]],
        root_conditions: List[Dict[str, Any]],
    ):
        self.database: str = config.database
        self.paths: Dict[str, Set[str]] = paths
        self.root_conditions: List[Dict[str, Any]] = root_conditions
        self.config: DatabaseSettings = config
        self.extracted_ids: Dict[str, Set[Any]] = defaultdict(set)
        with self.cursor as cursor:
            self.primary_keys: Dict[str, str] = self._get_primary_keys(cursor)
            self.foreign_keys: Dict[str, List[ForeignKey]] = self._get_foreign_keys(
                cursor
            )
            self.column_types: Dict[Tuple[str, str], str] = self._get_column_types(
                cursor
            )

    @property
    @contextmanager
    def cursor(self):
        with mysql.connector.connect(**self.config.model_dump()) as conn:
            with conn.cursor(dictionary=True) as cursor:
                yield cursor

    def _get_primary_keys(self, cursor) -> Dict[str, str]:
        cursor.execute(SQLStatements.PK, (self.database,))
        return {row["TABLE_NAME"]: row["COLUMN_NAME"] for row in cursor.fetchall()}

    def _get_foreign_keys(self, cursor) -> Dict[str, List[ForeignKey]]:
        cursor.execute(SQLStatements.FK, (self.database,))
        fks: Dict[str, List[ForeignKey]] = defaultdict(list)

        for row in cursor.fetchall():
            # For up foreign keys (from table to referenced table)
            fks[row["TABLE_NAME"]].append(
                ForeignKey(
                    ref_table=row["REFERENCED_TABLE_NAME"],
                    column=row["COLUMN_NAME"],
                    ref_column=row["REFERENCED_COLUMN_NAME"],
                )
            )

            # For down foreign keys (from referenced table to table)
            fks[row["REFERENCED_TABLE_NAME"]].append(
                ForeignKey(
                    ref_table=row["TABLE_NAME"],
                    column=row["REFERENCED_COLUMN_NAME"],
                    ref_column=row["COLUMN_NAME"],
                )
            )
        return fks

    def _get_column_types(self, cursor) -> Dict[Tuple[str, str], str]:
        cursor.execute(SQLStatements.COLUMN_TYPES, (self.config.database,))
        return {
            (row["TABLE_NAME"], row["COLUMN_NAME"]): row["DATA_TYPE"]
            for row in cursor.fetchall()
        }

    def _dump_rows(
        self, cursor, table: str, where_clause: str
    ) -> Tuple[Set[Tuple[str, Tuple]], List[Dict]]:
        cursor.execute(f"SELECT * FROM {table} WHERE {where_clause}")
        rows = cursor.fetchall()
        if not rows:
            return set(), []

        columns = [col[0] for col in cursor.description]
        inserts = {dump_row(row, columns, table, self.column_types) for row in rows}
        return inserts, rows

    def _process_foreign_keys(
        self,
        tables: Tuple[str, ...],
        rows: List[Dict],
    ) -> List[Tuple[Tuple[str, ...], str]]:
        queue = []
        table = tables[-1]
        for fk in self.foreign_keys.get(table, []):
            if fk.ref_table not in self.paths.get(table, set()):
                # only follow foreign keys that are indicated in self.paths
                continue

            if fk.ref_table in tables:
                # avoid cycles
                continue

            ids = {row.get(fk.column) for row in rows if row.get(fk.column) is not None}
            new_ids = ids - self.extracted_ids[fk.ref_table]
            if not new_ids:
                continue

            self.extracted_ids[fk.ref_table].update(new_ids)

            id_list = ",".join(format_value(i) for i in new_ids)

            queue.append((tables + (fk.ref_table,), f"{fk.ref_column} IN ({id_list})"))
        return queue

    def dump(self) -> Set[Tuple[str, Tuple]]:
        queue = [
            ((entry['table'],), build_where_clause(entry['clause']))
            for entry in self.root_conditions
        ]

        visited = set()
        output = set()

        with self.cursor as cursor:
            while queue:
                next_item = queue.pop(0)
                if next_item in visited:
                    continue
                visited.add(next_item)
                tables, where_clause = next_item

                inserts, rows = self._dump_rows(cursor, tables[-1], where_clause)
                output.update(inserts)

                queue.extend(self._process_foreign_keys(tables, rows))

        return output
