import os
import subprocess
import sys
from pathlib import Path


def test_alembic_upgrade_head_from_empty_database(tmp_path):
    backend_dir = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "migration_check.db"

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert database_path.exists()
