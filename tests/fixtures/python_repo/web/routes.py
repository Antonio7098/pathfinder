from pkg.service import get_user


def handler() -> dict[str, int]:
    return get_user()
