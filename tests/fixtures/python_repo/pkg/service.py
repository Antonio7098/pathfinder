from pkg.db import query_user


def get_user() -> dict[str, int]:
    return query_user()
