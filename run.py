import logging
import sys

from src.config.config import Config, ConfigError


def main() -> int:
    logging.basicConfig(
        level=Config.LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        Config.validate_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("Check your .env file (see .env.example).", file=sys.stderr)
        return 1

    from src.app import create_app

    app = create_app()
    print(f"Outlook Signature Manager on http://{Config.HOST}:{Config.PORT}")
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
