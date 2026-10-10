"""Launch with: uv run python -m web_api.main"""

import uvicorn


def main() -> None:
    # NEVER change this to 0.0.0.0 without adding authentication first.
    uvicorn.run("web_api.app:app", host="127.0.0.1", port=8010, reload=False)


if __name__ == "__main__":
    main()
