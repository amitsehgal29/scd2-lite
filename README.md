# scd2-lite

A tiny, standard-library-only CLI that applies a fresh source snapshot to a Type 2 slowly changing dimension (SCD2). Instead of overwriting old values, it keeps a dated history of every change, the way a warehouse dimension table does.

Given the current dimension and today's snapshot, matched on a business key:

- **Unchanged** keys keep their current row.
- **Changed** keys get their current row closed (`valid_to` = the as-of date, `is_current` = false), and a new current row is opened.
- **New** keys get a new current row.
- **Missing** keys are closed. Use `--keep-deleted` to leave them open instead.
- History rows are carried through untouched, and running it again with the same snapshot changes nothing.

It refuses to run when the snapshot has duplicate keys, or when the dimension already has two current rows for one key.

## Usage

```bash
python3 scd2_lite.py samples/dim_customer.csv samples/snapshot.csv \
  --key customer_id --as-of 2026-10-12
```

```csv
customer_id,name,city,tier,valid_from,valid_to,is_current
C1,Ali,Dubai,gold,2026-01-01,2026-06-01,false
C1,Ali,Abu Dhabi,gold,2026-06-01,9999-12-31,true
C2,Neha,Pune,silver,2026-03-15,2026-10-12,false
C2,Neha,Dubai,silver,2026-10-12,9999-12-31,true
C3,Sam,London,bronze,2026-04-10,2026-10-12,false
C4,Lee,Sharjah,bronze,2026-10-12,9999-12-31,true
```

A one-line summary goes to stderr: `{"unchanged": 1, "changed": 1, "inserted": 1, "deleted": 1}`.

Options:

- `--track name,city` compares only those columns. By default it compares every non-key column in the snapshot.
- `-o dim_new.csv` writes the result to a file.
- A header-only dimension file works for the first load.

## Tests

```bash
python3 -m unittest
```
