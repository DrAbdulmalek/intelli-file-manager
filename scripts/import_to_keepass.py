#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_to_keepass.py — استيراد ملفات الاعتماد إلى قاعدة .kdbx مشفّرة.

ضمانات:
  - كلمة المرور الرئيسية عبر getpass فقط (بلا echo، بلا log)
  - لا يُطبع أي بريد/كلمة مرور/URL
  - الحفظ ذرّي (pykeepass save → temp → rename)
  - Idempotent (dedup بـSHA-256 للمحتوى)
  - لا حذف للأصول قبل --verify ناجح + تأكيد صريح
"""
import argparse
import getpass
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from pykeepass import PyKeePass, create_database
    from pykeepass.exceptions import CredentialsError
except ImportError:
    print("ERROR: pykeepass not installed. Run:", file=sys.stderr)
    print("  python -m venv ~/rotation-venv", file=sys.stderr)
    print("  ~/rotation-venv/bin/pip install pykeepass", file=sys.stderr)
    sys.exit(1)

SCAN_ROOTS = [
    Path("/run/media/xorthomson/My Passport/NewFolder/fiinote_export"),
    Path("/run/media/xorthomson/My Passport/NewFolder/سلة_تحقق"),
    Path("/run/media/xorthomson/My Passport/NewFolder/وثائق"),
]
VAULT_DIR = Path.home() / "secure" / "vault-2026-11-27"

# صيغة: email_password _ Expiry
FIINOTE_RE = re.compile(r"^([^@\s]+@[^_\s]+)_([^_]+?)(?:\s+_\s+(.+))?$")


def discover():
    found = []
    seen = set()
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            n = p.name
            if ("@" in n) and ("expiry" in n.lower()) and str(p) not in seen:
                found.append((p, "fiinote")); seen.add(str(p))
    if VAULT_DIR.exists():
        for p in VAULT_DIR.iterdir():
            if p.is_file() and p.suffix.lower() == ".txt" and p.stat().st_size > 100:
                found.append((p, "vault"))
    return found


def parse_fiinote(path: Path):
    m = FIINOTE_RE.match(path.stem)
    if not m:
        return None
    email, password, _ = m.group(1), m.group(2).strip(), m.group(3)
    return {"name": f"fiinote:{email}", "username": email,
            "password": password, "url": ""}


def parse_vault(path: Path):
    entries = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n\r")
                if not line.strip() or line.lower().startswith("name,url"):
                    continue
                parts = line.split(",", 3)
                if len(parts) != 4:
                    continue
                name, url, user, pw = parts
                entries.append({"name": name or url or "unnamed",
                                "username": user, "password": pw, "url": url})
    except (IOError, UnicodeError):
        pass
    return entries


def entry_hash(e):
    return hashlib.sha256(
        f"{e['url']}|{e['username']}|{e['password']}".encode()
    ).hexdigest()


def _master_pw(create=False):
    if create:
        pw1 = getpass.getpass("New master password (>=12 chars): ")
        pw2 = getpass.getpass("Confirm: ")
        if pw1 != pw2:
            print("ERROR: mismatch", file=sys.stderr); sys.exit(1)
        if len(pw1) < 12:
            print("ERROR: too short", file=sys.stderr); sys.exit(1)
        return pw1
    return getpass.getpass("Master password: ")


def open_db(kdbx: Path, create_if_missing=True):
    if kdbx.exists():
        pw = _master_pw()
        try:
            return PyKeePass(str(kdbx), password=pw)
        except CredentialsError:
            print("ERROR: wrong master password", file=sys.stderr); sys.exit(1)
    if not create_if_missing:
        print(f"ERROR: {kdbx} not found", file=sys.stderr); sys.exit(1)
    pw = _master_pw(create=True)
    return create_database(str(kdbx), password=pw)


def ensure_group(kp, name):
    g = kp.find_groups(name=name, first=True)
    return g or kp.add_group(kp.root_group, name)


def existing_hashes(kp):
    hs = set()
    for e in kp.entries:
        hs.add(hashlib.sha256(
            f"{e.url or ''}|{e.username or ''}|{e.password or ''}".encode()
        ).hexdigest())
    return hs


def cmd_scan(_args):
    found = discover()
    fiinote = sum(1 for _, k in found if k == "fiinote")
    vault = sum(1 for _, k in found if k == "vault")
    total = 0
    for p, kind in found:
        if kind == "fiinote":
            total += 1 if parse_fiinote(p) else 0
        else:
            total += len(parse_vault(p))
    print("Discovered:")
    print(f"  fiinote credential files: {fiinote}")
    print(f"  vault CSV files: {vault}")
    print(f"  total entries to import: {total}")


def cmd_import(args):
    kdbx = Path(args.kdbx).expanduser()
    found = discover()
    if not found:
        print("Nothing to import.", file=sys.stderr); sys.exit(1)
    kp = open_db(kdbx)
    existing = existing_hashes(kp)
    target = ensure_group(kp, "Imported")
    for n in ("CRITICAL", "HIGH", "LOW", "DEAD"):
        ensure_group(kp, n)

    added = skipped = failed = 0
    for path, kind in found:
        try:
            entries = ([parse_fiinote(path)] if kind == "fiinote"
                       else parse_vault(path))
            entries = [e for e in entries if e]
        except Exception:
            failed += 1; continue
        for e in entries:
            h = entry_hash(e)
            if h in existing:
                skipped += 1; continue
            try:
                kp.add_entry(target, title=e["name"],
                             username=e["username"],
                             password=e["password"], url=e["url"])
                existing.add(h); added += 1
            except Exception:
                failed += 1
    kp.save()

    print("Import complete:")
    print(f"  added: {added}")
    print(f"  skipped (dup): {skipped}")
    print(f"  failed: {failed}")
    print(f"  total in DB: {len(kp.entries)}")
    print("\nSource files NOT deleted.")
    print(f"Next: {sys.argv[0]} --verify --kdbx {kdbx}")


def _check_all_present(kp):
    existing = existing_hashes(kp)
    found = discover()
    present = missing = 0
    for path, kind in found:
        try:
            entries = ([parse_fiinote(path)] if kind == "fiinote"
                       else parse_vault(path))
            entries = [e for e in entries if e]
        except Exception:
            continue
        for e in entries:
            if entry_hash(e) in existing:
                present += 1
            else:
                missing += 1
    return present, missing, len(found)


def cmd_verify(args):
    kdbx = Path(args.kdbx).expanduser()
    kp = open_db(kdbx, create_if_missing=False)
    present, missing, files = _check_all_present(kp)
    print("Verify:")
    print(f"  present: {present}")
    print(f"  missing: {missing}")
    print(f"  source files: {files}")
    if missing:
        print("NOT SAFE to delete. Re-run --import.", file=sys.stderr)
        sys.exit(1)
    print("All present. Safe to run --delete-source with confirmation.")


def cmd_delete_source(args):
    kdbx = Path(args.kdbx).expanduser()
    kp = open_db(kdbx, create_if_missing=False)
    present, missing, files = _check_all_present(kp)
    if missing:
        print(f"ERROR: {missing} missing. Aborting.", file=sys.stderr); sys.exit(1)

    print(f"Verified: {present} entries present in DB.")
    print(f"Files to delete: {files}")
    print("Type DELETE to permanently remove source files:")
    if input("> ").strip() != "DELETE":
        print("Aborted."); sys.exit(0)

    deleted = failed = 0
    for path, _ in discover():
        try:
            if shutil.which("shred"):
                subprocess.run(["shred", "-vfz", "-n", "3", str(path)],
                               check=True, capture_output=True)
            else:
                path.unlink()
            deleted += 1
        except Exception:
            failed += 1
    print(f"Deleted: {deleted}, Failed: {failed}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--import", dest="do_import", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--delete-source", action="store_true")
    ap.add_argument("--kdbx", type=str)
    a = ap.parse_args()
    if a.scan: return cmd_scan(a)
    if a.do_import:
        if not a.kdbx: ap.error("--kdbx required")
        return cmd_import(a)
    if a.verify:
        if not a.kdbx: ap.error("--kdbx required")
        return cmd_verify(a)
    if a.delete_source:
        if not a.kdbx: ap.error("--kdbx required")
        return cmd_delete_source(a)
    ap.print_help()


if __name__ == "__main__":
    main()