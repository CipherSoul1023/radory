"""Create ignored local development environment files without overwriting edits."""

from pathlib import Path
from secrets import token_hex

ROOT = Path(__file__).resolve().parents[1]
root_env = ROOT / ".env"
frontend_env = ROOT / "frontend" / ".env.local"

if not root_env.exists():
    password = token_hex(16)
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    example = example.replace("POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={password}\n")
    root_env.write_text(example, encoding="utf-8")
    print("Created .env; add managed DATABASE_URL and REDIS_URL values before starting")
else:
    print(".env already exists; left unchanged")

if not frontend_env.exists():
    frontend_env.write_text(
        (ROOT / "frontend" / ".env.example").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    print("Created frontend/.env.local")
else:
    print("frontend/.env.local already exists; left unchanged")
