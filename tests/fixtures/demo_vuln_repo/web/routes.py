from admin.export import export_all_customers
from auth.session import current_user_from_token
from billing.payments import get_invoice_for_user


def handle_request(path: str, headers: dict[str, str], query: dict[str, str] | None = None) -> dict[str, object]:
    query = query or {}
    user = current_user_from_token(headers.get("Authorization", ""))

    if path == "/invoice":
        invoice_id = query.get("invoice_id", "")
        return get_invoice_for_user(user, invoice_id)

    if path == "/admin/export":
        return export_all_customers(headers)

    return {"status": 404, "error": "not_found"}
