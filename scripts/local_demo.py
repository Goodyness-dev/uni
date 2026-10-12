"""Run the fictional local integration using real portable PostgreSQL and Redis.

Runtime binaries and credentials live under ignored storage/local_runtime.
Requires the documented portable binaries; never uses or resets another database.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RUNTIME = ROOT / "storage/local_runtime"


def configuration() -> dict[str, Any]:
    return json.loads((RUNTIME / "config.json").read_text(encoding="utf-8"))


def environment(agent: bool = False, notifications: bool = False) -> dict[str, str]:
    config = configuration()
    variables = os.environ.copy()
    variables.update(DATABASE_URL="postgresql+asyncpg://scholarpilot_admin:" + config["admin_password"]
        + "@127.0.0.1:" + str(config["pg_port"]) + "/" + config["database"],
        REDIS_URL="redis://:" + config["redis_password"] + "@127.0.0.1:" + str(config["redis_port"]) + "/0",
        ENVIRONMENT="development", LIVE_RESEARCH="true" if agent else "false", LLM_DRAFTING="false", DEBUG="false",
        KILL_SWITCH_ACTIVE="false", RETRY_SLEEP_SECONDS="0", DEMO_MODE="true",
        PUBLIC_BASE_URL="http://localhost:8000", NEXT_PUBLIC_API_VERSION="v1",
        NEXT_PUBLIC_USE_MOCKS="false", NEXT_PUBLIC_API_BASE="", API_BACKEND_URL="http://127.0.0.1:8001",
        TEST_DB_PATH=str(RUNTIME / "portal.db"))
    for name in ("NEATLOGS_API_KEY", "TELEGRAM_BOT_TOKEN", "SMTP_USER", "SMTP_APP_PASSWORD",
        "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "PRIMARY_API_KEY", "FALLBACK_API_KEY",
        "LLM_PRIMARY_API_KEY", "LLM_FALLBACK_API_KEY", "CRUSTDATA_API_KEY"):
        variables[name] = ""
    variables["AGENT_ENABLED"] = "true" if agent else "false"
    if agent:
        local_values = {}
        for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                local_values[name.strip()] = value.strip().strip("\"'")
        for name in ("GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_MODEL", "NEATLOGS_API_KEY", "NEATLOGS_ENDPOINT"):
            value = local_values.get(name)
            if value:
                variables[name] = value
        if not variables.get("GEMINI_API_KEY") or not variables.get("NEATLOGS_API_KEY"):
            raise ValueError("Agent demo requires real Gemini and Neatlogs credentials in ignored configuration.")
        variables["GEMINI_MODEL"] = local_values.get("AGENT_MODEL", "gemini-3.5-flash-lite")
        variables.update(LLM_DRAFTING="true", NEATLOGS_CAPTURE_CONTENT="false", LLM_MAX_RETRIES="1")
    if notifications:
        configured = {}
        for config_path in (ROOT / "backend/.env", ROOT / ".env"):
            if config_path.is_file():
                for line in config_path.read_text(encoding="utf-8").splitlines():
                    if "=" in line and not line.lstrip().startswith("#"):
                        name, value = line.split("=", 1)
                        configured[name.strip()] = value.strip().strip('"').strip("'")
        for name in ("TELEGRAM_BOT_TOKEN", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_APP_PASSWORD", "SMTP_FROM",
            "EMAIL_PROVIDER", "SES_FROM", "SES_REGION",
            "AWS_PROFILE",
            "OIDC_ISSUER", "OIDC_AUDIENCE", "OIDC_JWKS_URL", "OIDC_AUTHORIZATION_URL", "OIDC_TOKEN_URL", "OIDC_REDIRECT_URI"):
            if configured.get(name):
                variables[name] = configured[name]
        variables["NOTIFICATIONS_ENABLED"] = "true"
    return variables


def launch(name: str, arguments: list[str], cwd: Path, variables: dict[str, str]) -> None:
    pid_file = RUNTIME / (name + ".pid")
    if pid_file.exists() and os.name == "nt":
        identifier = int(pid_file.read_text())
        workspace = str(ROOT).replace("'", "''")
        probe = "$p = Get-CimInstance Win32_Process -Filter 'ProcessId = " + str(identifier) + "'; if ($p -and $p.CommandLine.Contains('" + workspace + "')) { exit 0 }; exit 1"
        if subprocess.run(["powershell", "-NoProfile", "-Command", probe], capture_output=True).returncode == 0:
            print(name + " already running")
            return
    with (RUNTIME / (name + ".log")).open("ab") as output:
        process = subprocess.Popen(arguments, cwd=cwd, env=variables, stdout=output,
            stderr=subprocess.STDOUT, creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_BREAKAWAY_FROM_JOB) if os.name == "nt" else 0)
    pid_file.write_text(str(process.pid), encoding="utf-8")
    print(name + " started, PID " + str(process.pid))


def wait_for(url: str) -> None:
    for _ in range(90):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(1)
    raise RuntimeError("Service did not become available: " + url)


async def seed() -> None:
    # The catalog contains real references, so only local portal fixtures are imported.
    sys.path.insert(0, str(ROOT))
    from scripts.import_catalog import import_listings
    catalog = json.loads((ROOT / "backend/data/listings.json").read_text(encoding="utf-8"))
    fixtures = [item for item in catalog["listings"] if item["is_mock"] and item["channel"] == "portal_form"]
    path = RUNTIME / "fictional_catalog.json"
    path.write_text(json.dumps({"listings": fixtures}), encoding="utf-8")
    count = await import_listings(path)
    print("Fictional portal catalog imported; new records:", count)


def start(agent: bool = False, notifications: bool = False) -> None:
    variables = environment(agent, notifications)
    subprocess.run([sys.executable, "-m", "compileall", "-q", str(ROOT / "app"), str(ROOT / "backend/app")], check=True)
    mode_file = RUNTIME / "runtime_mode.txt"
    if agent or (mode_file.exists() and mode_file.read_text().strip() == "agent"):
        stop_application_processes()
    os.environ.update(variables)
    pg_bin = RUNTIME / "postgres/pgsql/bin"
    # Redirect pg_ctl directly to a file: server descendants must not inherit a capture pipe.
    with (RUNTIME / "pg_control.log").open("ab") as output:
        check = subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(RUNTIME / "pgdata"), "status"], stdout=output, stderr=output)
        if check.returncode:
            subprocess.run([str(pg_bin / "pg_ctl.exe"), "-D", str(RUNTIME / "pgdata"), "-l", str(RUNTIME / "postgres.log"), "start", "-w"], stdout=output, stderr=output, check=True,
                creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0)
    asyncio.run(check_broker())
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=variables, check=True)
    asyncio.run(seed())
    launch("portal", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], ROOT / "backend", variables)
    launch("api", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"], ROOT, variables)
    wait_for("http://localhost:8000/api/health")
    wait_for("http://localhost:8001/ready")
    launch("worker", [sys.executable, "-m", "app.worker"], ROOT, variables)
    launch("frontend", ["C:/Program Files/nodejs/node.exe", str(ROOT / "frontend/node_modules/next/dist/bin/next"), "dev", "--hostname", "127.0.0.1", "--port", "3000"], ROOT / "frontend", variables)
    wait_for("http://localhost:3000")
    mode_file.write_text("agent" if agent else "extractive", encoding="utf-8")
    print("Frontend ready: http://localhost:3000 ; API: http://localhost:8001 ; portal: http://localhost:8000")


async def check_broker() -> None:
    import redis.asyncio as redis
    from redis.asyncio.retry import Retry
    from redis.backoff import NoBackoff
    config = configuration()
    client = redis.Redis(host="127.0.0.1", port=config["redis_port"], password=config["redis_password"], socket_connect_timeout=2, socket_timeout=2, retry=Retry(NoBackoff(), 0))
    try:
        await client.ping()
    except (redis.ConnectionError, redis.TimeoutError):
        binary = next((RUNTIME / "redis").rglob("redis-server.exe"))
        (binary.parent / "local-demo.conf").write_text((RUNTIME / "redis.conf").read_text(encoding="utf-8"), encoding="utf-8")
        launch("redis", [str(binary), "local-demo.conf"], binary.parent, environment())
        for _ in range(20):
            await asyncio.sleep(0.5)
            try:
                await client.ping()
                break
            except (redis.ConnectionError, redis.TimeoutError):
                continue
        else:
            raise RuntimeError("Real Redis server did not start.")
    finally:
        await client.aclose()


def stop_application_processes() -> None:
    # Stop only recorded processes after verifying their command targets this workspace.
    workspace = str(ROOT).replace("'", "''")
    for name in ("frontend", "worker", "api", "portal"):
        pid_path = RUNTIME / (name + ".pid")
        if not pid_path.exists():
            continue
        pid = int(pid_path.read_text())
        command = "function Stop-LocalDemoTree([int]$taskParent) { foreach ($taskChild in (Get-CimInstance Win32_Process -Filter ('ParentProcessId = ' + $taskParent))) { Stop-LocalDemoTree $taskChild.ProcessId }; Stop-Process -Id $taskParent -ErrorAction SilentlyContinue }; $p = Get-CimInstance Win32_Process -Filter 'ProcessId = " + str(pid) + "'; if ($p -and $p.CommandLine.Contains('" + workspace + "') -and $p.CommandLine -match 'uvicorn|app.worker|next') { Stop-LocalDemoTree " + str(pid) + " }"
        subprocess.run(["powershell", "-NoProfile", "-Command", command], check=False)
        # A stopped PID can be reused before the next launch. Never treat that
        # stale service marker as proof that the replacement service is running.
        pid_path.unlink(missing_ok=True)


def stop() -> None:
    stop_application_processes()
    subprocess.run([str(RUNTIME / "postgres/pgsql/bin/pg_ctl.exe"), "-D", str(RUNTIME / "pgdata"), "stop", "-m", "fast", "-w"], check=True)
    asyncio.run(stop_broker())
    print("Local demo stopped; fictional data and binaries retained.")


async def stop_broker() -> None:
    import redis.asyncio as redis
    from redis.asyncio.retry import Retry
    from redis.backoff import NoBackoff
    config = configuration()
    client = redis.Redis(host="127.0.0.1", port=config["redis_port"], password=config["redis_password"], socket_connect_timeout=2, socket_timeout=2, retry=Retry(NoBackoff(), 0))
    try:
        await client.shutdown(nosave=True)
    finally:
        await client.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "stop"), default="start", nargs="?")
    parser.add_argument("--agent", action="store_true", help="Enable live fictional model calls and Neatlogs export")
    parser.add_argument("--notifications", action="store_true", help="Enable configured real notification providers")
    args = parser.parse_args()
    start(args.agent, args.notifications) if args.action == "start" else stop()
