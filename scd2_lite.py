#!/usr/bin/env python3
"""scd2-lite: apply a source snapshot to a Type 2 slowly changing dimension.

Standard library only. Takes the current dimension CSV (with valid_from,
valid_to, is_current columns) and a fresh snapshot CSV of the source, matches
rows on a business key, and writes the new dimension:

  * unchanged keys keep their current row as is
  * changed keys get their current row closed (valid_to = as-of date,
    is_current = false) and a new current row opened from the as-of date
  * new keys get a new current row
  * keys missing from the snapshot are closed, or kept open with --keep-deleted

History rows (is_current = false) are always carried through untouched.
"""
import argparse
import csv
import json
import sys

META = ("valid_from", "valid_to", "is_current")
OPEN_END = "9999-12-31"


def is_current(row):
    return str(row.get("is_current", "")).strip().lower() in ("true", "1", "y", "yes")


def apply_snapshot(dim_rows, snap_rows, key, tracked, as_of, keep_deleted=False):
    """Return (new_dim_rows, stats). Rows are plain dicts of strings."""
    current, history = {}, []
    for r in dim_rows:
        if is_current(r):
            k = r[key]
            if k in current:
                raise ValueError(f"dimension has two current rows for key {k!r}")
            current[k] = r
        else:
            history.append(dict(r))

    snap = {}
    for r in snap_rows:
        k = r[key]
        if k in snap:
            raise ValueError(f"snapshot has duplicate key {k!r}")
        snap[k] = r

    out = list(history)
    stats = {"unchanged": 0, "changed": 0, "inserted": 0, "deleted": 0}

    for k, cur in current.items():
        new = snap.get(k)
        if new is None:
            if keep_deleted:
                out.append(dict(cur))
                stats["unchanged"] += 1
            else:
                out.append({**cur, "valid_to": as_of, "is_current": "false"})
                stats["deleted"] += 1
            continue
        if all((cur.get(c) or "") == (new.get(c) or "") for c in tracked):
            out.append(dict(cur))
            stats["unchanged"] += 1
        else:
            out.append({**cur, "valid_to": as_of, "is_current": "false"})
            out.append({**{c: new.get(c, "") for c in [key, *tracked]},
                        "valid_from": as_of, "valid_to": OPEN_END, "is_current": "true"})
            stats["changed"] += 1

    for k, new in snap.items():
        if k not in current:
            out.append({**{c: new.get(c, "") for c in [key, *tracked]},
                        "valid_from": as_of, "valid_to": OPEN_END, "is_current": "true"})
            stats["inserted"] += 1

    out.sort(key=lambda r: (r[key], r["valid_from"]))
    return out, stats


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def main(argv=None):
    p = argparse.ArgumentParser(description="Apply a snapshot to a Type 2 SCD dimension CSV.")
    p.add_argument("dimension", help="current dimension CSV (may be header-only)")
    p.add_argument("snapshot", help="source snapshot CSV")
    p.add_argument("--key", required=True, help="business key column")
    p.add_argument("--track", help="comma-separated columns to track (default: all non-key snapshot columns)")
    p.add_argument("--as-of", required=True, help="effective date for this load, e.g. 2026-10-12")
    p.add_argument("--keep-deleted", action="store_true", help="leave keys missing from the snapshot open")
    p.add_argument("-o", "--output", default="-", help="output CSV path (default: stdout)")
    args = p.parse_args(argv)

    _, dim = read_csv(args.dimension)
    snap_cols, snap = read_csv(args.snapshot)
    if args.key not in snap_cols:
        print(f"scd2-lite: key {args.key!r} not in snapshot columns {snap_cols}", file=sys.stderr)
        return 2
    tracked = [c.strip() for c in args.track.split(",")] if args.track else [c for c in snap_cols if c != args.key]
    missing = [c for c in tracked if c not in snap_cols]
    if missing:
        print(f"scd2-lite: tracked columns not in snapshot: {missing}", file=sys.stderr)
        return 2

    try:
        rows, stats = apply_snapshot(dim, snap, args.key, tracked, args.as_of, args.keep_deleted)
    except ValueError as e:
        print(f"scd2-lite: {e}", file=sys.stderr)
        return 2

    fields = [args.key, *tracked, *META]
    out = sys.stdout if args.output == "-" else open(args.output, "w", newline="", encoding="utf-8")
    try:
        w = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    finally:
        if out is not sys.stdout:
            out.close()
    print(json.dumps(stats), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
