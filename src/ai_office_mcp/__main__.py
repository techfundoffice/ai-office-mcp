import anyio

from ai_office_mcp.server import serve


def main() -> None:
    anyio.run(serve)


if __name__ == "__main__":
    main()
