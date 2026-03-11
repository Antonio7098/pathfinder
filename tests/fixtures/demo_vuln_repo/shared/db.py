FAKE_DB = {
    "invoice:inv-100": {
        "id": "inv-100",
        "owner_id": "user-123",
        "total": 4200,
        "card_last4": "4242",
    },
    "customers": [
        {"id": "cust-1", "email": "alice@example.com", "plan": "pro", "mrr": 120},
        {"id": "cust-2", "email": "bob@example.com", "plan": "enterprise", "mrr": 900},
    ],
}


def fetch_one(query: str) -> dict[str, object] | None:
    if "or '1'='1" in query.lower():
        return FAKE_DB["invoice:inv-100"]
    if "inv-100" in query:
        return FAKE_DB["invoice:inv-100"]
    return None


def fetch_all(query: str) -> list[dict[str, object]]:
    if "from customers" in query.lower():
        return list(FAKE_DB["customers"])
    return []
