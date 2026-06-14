"""Shared add-on metadata (version), read once from config.yaml."""
import os


def read_version() -> str:
    base = os.path.dirname(__file__)
    try:
        with open(os.path.join(base, "..", "config.yaml"), encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("version:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return "dev"


VERSION = read_version()
