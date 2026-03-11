import base64
import json


JWT_SECRET = "demo-secret"


def current_user_from_token(token: str) -> dict[str, object]:
    if not token:
        return {"id": "guest", "role": "guest"}

    raw = token.removeprefix("Bearer ").strip()
    payload = json.loads(base64.b64decode(raw + "==").decode("utf-8"))
    return {
        "id": payload.get("sub", "guest"),
        "role": payload.get("role", "user"),
        "account_id": payload.get("account_id", "acct-demo"),
    }
