"""Fetch instance-role protected configuration without logging secrets."""
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    result = subprocess.run(["aws", "secretsmanager", "get-secret-value", "--secret-id", sys.argv[1],
        "--region", "eu-north-1", "--output", "json"], check=True, capture_output=True, text=True, timeout=30)
    values = json.loads(json.loads(result.stdout)["SecretString"])
    lines = []
    for name, value in values.items():
        if not name.replace("_", "").isalnum() or "\n" in value or "\r" in value:
            raise ValueError("Invalid runtime configuration field.")
        # Compose single-quoted values preserve dollar signs and disable interpolation.
        lines.append(name + "='" + value.replace("'", "\\'") + "'")
    config = Path("deploy/.env")
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(config, 0o600)
    for name in ("screenshots", "documents", "packages", "portal"):
        path = Path("storage") / name
        path.mkdir(parents=True, exist_ok=True)
        os.chown(path, 1000, 1000)
    os.chown("storage", 1000, 1000)
    print("Private configuration written; persistent application directories prepared.")


if __name__ == "__main__":
    main()
