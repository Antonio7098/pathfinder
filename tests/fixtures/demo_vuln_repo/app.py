from web.routes import handle_request


def main() -> None:
    print(handle_request("/admin/export", {"X-Debug-Auth": "dev-mode"}))


if __name__ == "__main__":
    main()
