"""Create local-only configuration without printing or overwriting credentials."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / "backend/.env"
password = secrets.token_hex(24)
base_url = f"postgresql+asyncpg://dota_hub:{password}@127.0.0.1:55432"
content = (
    "DOTA_DOCS_ENABLED=true\nPOSTGRES_USER=dota_hub\nPOSTGRES_DB=dota_hub\n"
    f"POSTGRES_PASSWORD={password}\nDATABASE_URL={base_url}/dota_hub\n"
    f"TEST_DATABASE_URL={base_url}/dota_hub_test\n"
    f"MIGRATION_TEST_DATABASE_URL={base_url}/dota_hub_migration_test\n"
    "DOTA_DB_HEALTH_TIMEOUT_SECONDS=3\n"
)
try:
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit("backend/.env already exists; left unchanged") from None
with os.fdopen(descriptor, "w") as handle:
    handle.write(content)
print("Created backend/.env with local credentials (mode 0600); values are not displayed.")
