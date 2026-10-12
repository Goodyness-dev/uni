"""Ship an explicit source bundle to the private, selected-Region AWS host.

Requires the already reviewed CloudFormation stack. Secrets never enter the
archive, SSM commands, command output, or CloudFormation user data.
"""
import argparse
import json
import secrets
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "storage/local_runtime"
REGION = "eu-north-1"
STACK = "scholarpilot-hackathon"


def aws(arguments: list[str]) -> Any:
    result = subprocess.run(["aws", *arguments, "--profile", "UNI", "--region", REGION,
        "--cli-connect-timeout", "5", "--cli-read-timeout", "20", "--output", "json"],
        check=True, capture_output=True, text=True, timeout=90)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def bundle(destination: Path) -> list[str]:
    roots = ["app", "scripts", "frontend", "deploy", "backend/app", "backend/data/synthetic"]
    files = [ROOT / name for name in ["Dockerfile", ".dockerignore", "requirements.txt", "alembic.ini",
        "backend/data/listings.json", "backend/data/research_sources.json"]]
    excluded = {"node_modules", ".next", "__pycache__", ".pytest_cache", ".git", ".venv"}
    for root in roots:
        files.extend(path for path in (ROOT / root).rglob("*") if path.is_file()
            and not excluded.intersection(path.relative_to(ROOT).parts)
            and not path.name.startswith(".env") and path.suffix not in {".pyc", ".tsbuildinfo", ".log", ".db"})
    with tarfile.open(destination, "w:gz") as archive:
        for path in sorted(set(files)):
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    return [path.relative_to(ROOT).as_posix() for path in sorted(set(files))]


def configured_values() -> dict[str, str]:
    values = {}
    for source in (ROOT / "backend/.env", ROOT / ".env"):
        if source.is_file():
            for line in source.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    name, value = line.split("=", 1)
                    values[name.strip()] = value.strip().strip("\"'")
    return values


def runtime_values(outputs: dict[str, str], sender: str) -> dict[str, str]:
    from cryptography.fernet import Fernet
    secret = aws(["secretsmanager", "get-secret-value", "--secret-id", outputs["RuntimeSecret"]])
    existing = json.loads(secret["SecretString"])
    password = existing["POSTGRES_PASSWORD"]
    values = configured_values()
    redis_password = existing.get("REDIS_PASSWORD") or secrets.token_hex(24)
    env = {"POSTGRES_USER": "scholarpilot", "POSTGRES_DB": "scholarpilot_db", "POSTGRES_PASSWORD": password,
        "DATABASE_URL": "postgresql+asyncpg://scholarpilot:" + password + "@127.0.0.1:5432/scholarpilot_db",
        "REDIS_PASSWORD": redis_password, "REDIS_URL": "redis://:" + redis_password + "@127.0.0.1:6379/0",
        "ENVIRONMENT": "production", "DEBUG": "false", "DEMO_MODE": "true",
        "PUBLIC_BASE_URL": "http://localhost:8000", "AGENT_ENABLED": "true", "LIVE_RESEARCH": "true",
        "LLM_DRAFTING": "true", "NEATLOGS_CAPTURE_CONTENT": "false", "NOTIFICATIONS_ENABLED": "true",
        "EMAIL_PROVIDER": "ses", "SES_REGION": REGION, "SES_FROM": sender,
        "ENCRYPTION_KEY": existing.get("ENCRYPTION_KEY") or Fernet.generate_key().decode(),
        "SECRET_KEY": existing.get("SECRET_KEY") or secrets.token_urlsafe(32),
        "GEMINI_MODEL": values.get("AGENT_MODEL", "gemini-3.5-flash-lite"), "LLM_MAX_RETRIES": "1",
        "OIDC_ISSUER": outputs["Issuer"], "OIDC_AUDIENCE": outputs["ClientId"],
        "OIDC_JWKS_URL": outputs["Issuer"] + "/.well-known/jwks.json",
        "OIDC_AUTHORIZATION_URL": outputs["AuthBase"] + "/oauth2/authorize",
        "OIDC_TOKEN_URL": outputs["AuthBase"] + "/oauth2/token", "OIDC_REDIRECT_URI": "http://localhost:13000/"}
    for name in ("GEMINI_API_KEY", "GEMINI_BASE_URL", "NEATLOGS_API_KEY", "NEATLOGS_ENDPOINT", "TELEGRAM_BOT_TOKEN"):
        if values.get(name):
            env[name] = values[name]
    if not env.get("GEMINI_API_KEY") or not env.get("NEATLOGS_API_KEY"):
        raise ValueError("Live deployment requires private model and Neatlogs configuration.")
    return env


def deploy(sender: str) -> dict[str, str]:
    stacks = aws(["cloudformation", "describe-stacks", "--stack-name", STACK])["Stacks"]
    if stacks[0]["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
        raise ValueError("Wait for the CloudFormation stack to complete before shipping.")
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stacks[0]["Outputs"]}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    release = RUNTIME / "release.tgz"
    names = bundle(release)
    (RUNTIME / "release_manifest.json").write_text(json.dumps(names, indent=2))
    aws(["s3api", "put-object", "--bucket", outputs["ArtifactBucket"], "--key", "release.tgz",
        "--body", str(release), "--server-side-encryption", "AES256"])
    private = RUNTIME / "aws_secret_values.json"
    private.write_text(json.dumps(runtime_values(outputs, sender)), encoding="utf-8")
    try:
        aws(["secretsmanager", "put-secret-value", "--secret-id", outputs["RuntimeSecret"],
            "--secret-string", "file://" + str(private)])
    finally:
        private.unlink(missing_ok=True)
    commands = ["set -eu", "mkdir -p /opt/scholarpilot", "cd /opt/scholarpilot",
        "aws s3 cp s3://" + outputs["ArtifactBucket"] + "/release.tgz release.tgz --region " + REGION,
        "tar -xzf release.tgz", "python3 deploy/bootstrap_host.py " + outputs["RuntimeSecret"],
        "docker compose --parallel 1 -f deploy/compose.yml build",
        "docker compose -f deploy/compose.yml up -d", "docker compose -f deploy/compose.yml ps"]
    parameters = RUNTIME / "aws_ssm_commands.json"
    parameters.write_text(json.dumps({"commands": commands, "executionTimeout": ["3600"]}))
    result = aws(["ssm", "send-command", "--document-name", "AWS-RunShellScript", "--instance-ids",
        outputs["InstanceId"], "--parameters", "file://" + str(parameters), "--timeout-seconds", "3600",
        "--cloud-watch-output-config", "CloudWatchLogGroupName=" + outputs["CommandLogs"] + ",CloudWatchOutputEnabled=true"])
    outputs["CommandId"] = result["Command"]["CommandId"]
    (RUNTIME / "aws_deployment.json").write_text(json.dumps(outputs, indent=2))
    return {"command_id": outputs["CommandId"], "status": "remote_build_queued"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sender", required=True)
    args = parser.parse_args()
    print(json.dumps(deploy(args.sender)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
