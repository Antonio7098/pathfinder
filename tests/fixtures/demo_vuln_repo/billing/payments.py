from shared.db import fetch_one


def get_invoice_for_user(user: dict[str, object], invoice_id: str) -> dict[str, object]:
    query = (
        "select id, owner_id, total, card_last4 from invoices "
        f"where id = '{invoice_id}'"
    )
    invoice = fetch_one(query)
    if invoice is None:
        return {"status": 404, "error": "missing"}

    return {
        "status": 200,
        "invoice": invoice,
        "requested_by": user.get("id"),
    }
