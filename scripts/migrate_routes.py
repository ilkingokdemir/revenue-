#!/usr/bin/env python3
"""
Safely migrate route files from /app/backend/routes/ into a domain subfolder.

Usage:
    python migrate_routes.py <dest_dir> file1 file2 file3 ...

Process per file:
  1. git mv routes/<file>.py routes/<dest_dir>/<file>.py
  2. sed-replace `from routes.<file>` -> `from routes.<dest_dir>.<file>` in server.py
  3. Skip any file that already lives in a subfolder or doesn't exist

After all moves it prints a summary. Caller is responsible for restarting backend
and running smoke tests.
"""
import sys
import os
import re
import shutil
import subprocess
from pathlib import Path

ROUTES_DIR = Path("/app/backend/routes")
SERVER_PY = Path("/app/backend/server.py")


def run(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def migrate_one(filename: str, dest: str) -> tuple[bool, str]:
    """Move one file & update its import line in server.py."""
    src = ROUTES_DIR / f"{filename}.py"
    dst_dir = ROUTES_DIR / dest
    dst = dst_dir / f"{filename}.py"

    if not src.exists():
        return False, f"SKIP {filename}: src does not exist (already moved?)"
    if not dst_dir.exists():
        return False, f"SKIP {filename}: dest dir {dest} does not exist"

    # Ensure __init__.py exists in dest
    init_py = dst_dir / "__init__.py"
    if not init_py.exists():
        init_py.touch()

    # Move file (prefer git mv to preserve history)
    code, out, err = run(f"git -C /app mv backend/routes/{filename}.py backend/routes/{dest}/{filename}.py")
    if code != 0:
        # Fallback to plain move
        try:
            shutil.move(str(src), str(dst))
        except Exception as e:
            return False, f"FAIL {filename}: move error: {e}; git err: {err}"

    # Update server.py imports
    text = SERVER_PY.read_text()
    old_pattern = re.compile(rf"from routes\.{re.escape(filename)} import")
    new_text, count = old_pattern.subn(f"from routes.{dest}.{filename} import", text)
    if count == 0:
        return True, f"MOVED {filename} -> {dest}/  (no import line found in server.py)"
    SERVER_PY.write_text(new_text)
    return True, f"MOVED {filename} -> {dest}/  ({count} import line(s) updated)"


def main():
    if len(sys.argv) < 3:
        print("Usage: migrate_routes.py <dest_dir> file1 [file2 ...]")
        sys.exit(2)
    dest = sys.argv[1]
    files = sys.argv[2:]
    results = []
    for f in files:
        ok, msg = migrate_one(f, dest)
        results.append((ok, msg))
        print(msg)
    print("\n--- summary ---")
    print(f"total={len(files)} ok={sum(1 for r in results if r[0])} skipped/failed={sum(1 for r in results if not r[0])}")


if __name__ == "__main__":
    main()
