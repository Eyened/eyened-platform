import os


def collect_rows(rows):
    def to_dict(row):
        return {
            k: v for k, v in row.to_dict().items() if k not in ("ValueBlob", "FormData")
        }

    return [
        to_dict(row)
        for row in rows
        # the tuples (None, None) are returned by the tags linking tables
        if (row is not None) and (row != (None, None))
    ]
