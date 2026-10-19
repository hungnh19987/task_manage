"""Create and rotate PostgreSQL backups using pg_dump."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import config

BACKUP_PREFIX = "app_"
BACKUP_SUFFIX = ".dump"


def backup(dest_dir: Path, keep: int) -> Path:
    parsed = urlparse(config.get_database_url())
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname:
        raise ValueError("DATABASE_URL phải là URL PostgreSQL hợp lệ.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = dest_dir / f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"
    environment = os.environ.copy()
    if parsed.password:
        environment["PGPASSWORD"] = unquote(parsed.password)
    sslmode = parse_qs(parsed.query).get("sslmode", [None])[0]
    if sslmode:
        environment["PGSSLMODE"] = sslmode

    command = [
        "pg_dump",
        "--host", parsed.hostname,
        "--port", str(parsed.port or 5432),
        "--username", unquote(parsed.username or ""),
        "--dbname", unquote(parsed.path.lstrip("/")),
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file", str(dest_path),
    ]
    try:
        subprocess.run(command, env=environment, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        dest_path.unlink(missing_ok=True)
        raise RuntimeError("pg_dump không thành công. Kiểm tra cài đặt PostgreSQL client và kết nối Supabase.") from exc

    if keep > 0:
        old = sorted(dest_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"))[:-keep]
        for path in old:
            path.unlink()
    return dest_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sao lưu PostgreSQL.")
    parser.add_argument("--dest", type=Path, default=config.BACKUP_DIR, help="Thư mục lưu bản sao lưu")
    parser.add_argument("--keep", type=int, default=30, help="Số bản mới nhất cần giữ (0 = giữ tất cả)")
    args = parser.parse_args(argv)
    try:
        path = backup(args.dest, args.keep)
    except (RuntimeError, ValueError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
    print(f"Đã sao lưu: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())