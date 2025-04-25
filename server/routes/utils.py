import functools
import os
from hashlib import pbkdf2_hmac


class ordered_partial(functools.partial):
    """
    Slightly modified version of functools.partial which changes the
    order in which the declared arguments and the new arguments are passed
    to the function
    """

    def __call__(*args, **keywords):
        # This is the old way (before 3.8) of using only positional arguments
        if not args:
            raise TypeError("descriptor '__call__' of partial needs an argument")
        self, *args = args
        # allow overwriting the declared keywords
        keywords = {**self.keywords, **keywords}
        return self.func(*args, *self.args, **keywords)


def password_hash(password: str):
    return pbkdf2_hmac(
        "sha256", password.encode(), os.environ["SECRET_KEY"].encode(), 10000
    )


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
