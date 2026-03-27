from html import escape

from sqlalchemy.orm import DeclarativeBase


class EyeNedDeclarativeDisplayMeta(type(DeclarativeBase)):
    """Adds rich notebook display for ORM model classes (e.g. `Patient`)."""

    def _column_info_rows(cls) -> list[dict[str, str]]:
        table = getattr(cls, "__table__", None)
        if table is None:
            return []

        rows: list[dict[str, str]] = []
        for column in table.columns:
            fk_targets = [
                f"{fk.column.table.name}.{fk.column.name}" for fk in column.foreign_keys
            ]
            rows.append(
                {
                    "Column": column.name,
                    "Type": str(column.type),
                    "Nullable": "yes" if column.nullable else "no",
                    "PK": "yes" if column.primary_key else "no",
                    "FK": ", ".join(fk_targets) if fk_targets else "",
                    "Unique": "yes" if bool(column.unique) else "no",
                    "Indexed": "yes" if bool(column.index) else "no",
                }
            )
        return rows

    def _repr_html_(cls) -> str:
        """Render class objects as a schema table in Jupyter."""
        rows = cls._column_info_rows()
        title = escape(cls.__name__)

        if not rows:
            return f"<div><strong>{title}</strong><br><em>No mapped columns.</em></div>"

        headers = list(rows[0].keys())
        th_html = "".join(
            f"<th style='text-align:left;padding:6px 8px;border-bottom:1px solid #e5e7eb;background:#f6f7f8'>{escape(header)}</th>"
            for header in headers
        )
        tr_html = []
        for row in rows:
            tds = "".join(
                f"<td style='padding:4px 8px;border-bottom:1px solid #e5e7eb;vertical-align:top'>{escape(value)}</td>"
                for value in row.values()
            )
            tr_html.append(f"<tr>{tds}</tr>")

        return (
            f"<div style='margin:4px 0'>"
            f"<h4 style='margin:0 0 6px 0;font-size:14px;font-weight:600'>{title} schema</h4>"
            f"<table style='border-collapse:collapse;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;font-size:12px'>"
            f"<thead><tr>{th_html}</tr></thead>"
            f"<tbody>{''.join(tr_html)}</tbody>"
            f"</table>"
            f"</div>"
        )

    def _repr_markdown_(cls) -> str:
        """Fallback for frontends that prefer markdown rendering."""
        rows = cls._column_info_rows()
        if not rows:
            return f"**{cls.__name__}**\n\n_No mapped columns._"

        headers = list(rows[0].keys())
        header_row = "| " + " | ".join(headers) + " |"
        separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        data_rows = "\n".join(
            "| " + " | ".join(row[header] for header in headers) + " |"
            for row in rows
        )
        return f"**{cls.__name__} schema**\n\n{header_row}\n{separator_row}\n{data_rows}"
