"""Tạo database và schema (an toàn khi chạy lại).

Chạy từ thư mục gốc dự án:  python -m scripts.init_db
"""
from __future__ import annotations

from core import database


def main() -> int:
    database.init_db()
    print("Đã khởi tạo schema PostgreSQL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
