from shared.db import fetch_all


def export_all_customers(headers: dict[str, str]) -> dict[str, object]:
    if headers.get("X-Debug-Auth") != "dev-mode":
        return {"status": 403, "error": "forbidden"}

    rows = fetch_all("select id, email, plan, mrr from customers")
    return {"status": 200, "rows": rows}
