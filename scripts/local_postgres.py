"""Optional macOS PostgreSQL fallback when Docker is unavailable; no system service."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
runtime = root / ".local"
data = runtime / "postgres"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=["start", "stop", "status", "create-databases"])
parser.add_argument("--bin", default="/opt/homebrew/opt/postgresql@17/bin")
args = parser.parse_args()
binary = Path(args.bin)
if not (binary / "pg_ctl").is_file():
    raise SystemExit("PostgreSQL 17 binaries not found; install them or supply --bin")
runtime.mkdir(mode=0o700, exist_ok=True)
values = dotenv_values(root / "backend/.env")
if values.get("POSTGRES_USER") != "dota_hub" or values.get("POSTGRES_DB") != "dota_hub":
    raise SystemExit("This local helper requires the dedicated dota_hub configuration")
password = values.get("POSTGRES_PASSWORD")
if not password or password.startswith("<"):
    raise SystemExit("Generate backend/.env first; placeholders cannot be used")


def run(
    command: list[str], *, capture_output: bool = False,
    env: dict[str, str] | None = None, stdout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=capture_output, env=env, stdout=stdout)


control = [str(binary / "pg_ctl"), "-D", str(data)]
if args.action == "start":
    if not (data / "PG_VERSION").exists():
        if data.exists() and any(data.iterdir()):
            raise SystemExit("Refusing to initialize a nonempty data directory")
        with tempfile.NamedTemporaryFile(mode="w", dir=runtime) as handle:
            handle.write(password)
            handle.flush()
            run([str(binary / "initdb"), "-D", str(data), "--username=dota_hub",
                 "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C", f"--pwfile={handle.name}"], stdout=subprocess.DEVNULL)
    status = subprocess.run(control + ["status"], capture_output=True)
    if status.returncode == 0:
        print("Project PostgreSQL is already running")
    else:
        run(control + ["-l", str(runtime / "postgres.log"), "-o", "-h 127.0.0.1 -p 55432 -k ''", "-w", "start"])
elif args.action in {"stop", "status"}:
    run(control + (["-m", "fast", "-w", "stop"] if args.action == "stop" else ["status"]))
else:
    environment = {**os.environ, "PGPASSWORD": password}
    connection = ["--host=127.0.0.1", "--port=55432", "--username=dota_hub"]
    for name in ("dota_hub", "dota_hub_test", "dota_hub_migration_test"):
        check = run([str(binary / "psql"), *connection, "--dbname=postgres", "-Atc",
                     f"SELECT 1 FROM pg_database WHERE datname = '{name}'"], env=environment, capture_output=True)
        if check.stdout.strip() != "1":
            run([str(binary / "createdb"), *connection, name], env=environment)
        print(f"Database ready: {name}")
