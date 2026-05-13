"""Find unregistered (orphaned) files in an r2d2 local data store.

Two-phase approach:

  Phase 1 (--scan):  Walk the data store filesystem and write a CSV of all files found.
                     This only needs to be run once per data store (may be slow for large stores).

  Phase 2 (--check): Read the scan CSV and check each file against the r2d2 API.
                     Writes a new CSV listing only orphaned (unregistered) files.
                     Requires R2D2_* env vars (R2D2_USER, R2D2_HOST, R2D2_COMPILER, R2D2_API_KEY).

Usage:
    # Step 1 – scan the filesystem (run once):
    python find_unregistered_files.py --scan \\
        --basedir /css/jcsda/s2127 \\
        --data-store r2d2-experiments-nccs \\
        --files-csv files_nccs.csv

    # Step 2 – check against r2d2:
    python find_unregistered_files.py --check \\
        --files-csv files_nccs.csv \\
        --output orphans_nccs.csv

    # Or run both phases in one go:
    python find_unregistered_files.py --scan --check \\
        --basedir /css/jcsda/s2127 \\
        --data-store r2d2-experiments-nccs \\
        --files-csv files_nccs.csv \\
        --output orphans_nccs.csv

File path structure on disk:
    <basedir>/<data_store>/<item>/<date>/<index>.<extension>
"""

import argparse
import csv
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Items that write files to disk (mirrors r2d2 DATA_ITEMS)
DATA_ITEMS = {
    'analysis', 'bias_correction', 'diagnostic',
    'feedback', 'forecast', 'media', 'observation',
}

SCAN_FIELDNAMES = ['filepath', 'item', 'date', 'index', 'extension', 'size_bytes']
ORPHAN_FIELDNAMES = ['filepath', 'item', 'date', 'index', 'extension', 'size_bytes', 'size_mb', 'size_gb']
SYMLINK_FIELDNAMES = ['filepath', 'item', 'date', 'index', 'extension', 'target', 'target_exists']


# ---------------------------------------------------------------------------
# Phase 1 – filesystem scan
# ---------------------------------------------------------------------------

def scan_data_store(basedir: str, data_store: str, files_csv: str, symlinks_csv: str = None):
    """Walk the data store and write every leaf file to files_csv.

    Only regular (non-symlink) files are written to files_csv.
    All symlinks (live or dangling) are written to symlinks_csv (if provided).
    """
    root = os.path.join(basedir, data_store)
    if not os.path.isdir(root):
        raise FileNotFoundError(f'Data store directory not found: {root}')

    logger.info(f'Scanning: {root}')
    count = 0
    symlink_count = 0

    symlink_writer = None
    symlink_f = None
    if symlinks_csv:
        symlink_f = open(symlinks_csv, 'w', newline='')
        symlink_writer = csv.DictWriter(symlink_f, fieldnames=SYMLINK_FIELDNAMES)
        symlink_writer.writeheader()

    try:
        with open(files_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=SCAN_FIELDNAMES)
            writer.writeheader()

            for item_entry in os.scandir(root):
                if not item_entry.is_dir() or item_entry.name not in DATA_ITEMS:
                    continue
                item_name = item_entry.name

                for date_entry in os.scandir(item_entry.path):
                    if not date_entry.is_dir():
                        continue
                    date_str = date_entry.name

                    for file_entry in os.scandir(date_entry.path):
                        base, ext = os.path.splitext(file_entry.name)
                        try:
                            index = int(base)
                        except ValueError:
                            logger.warning(f'Skipping unexpected filename: {file_entry.path}')
                            continue

                        # Symlink (live or dangling) → symlinks CSV only
                        if file_entry.is_symlink():
                            symlink_count += 1
                            if symlink_writer:
                                symlink_writer.writerow({
                                    'filepath':      file_entry.path,
                                    'item':          item_name,
                                    'date':          date_str,
                                    'index':         index,
                                    'extension':     ext.lstrip('.'),
                                    'target':        os.readlink(file_entry.path),
                                    'target_exists': file_entry.is_file(follow_symlinks=True),
                                })
                            continue

                        # Regular file only
                        if not file_entry.is_file(follow_symlinks=False):
                            continue
                        size_bytes = file_entry.stat(follow_symlinks=False).st_size
                        writer.writerow({
                            'filepath':   file_entry.path,
                            'item':       item_name,
                            'date':       date_str,
                            'index':      index,
                            'extension':  ext.lstrip('.'),
                            'size_bytes': size_bytes,
                        })
                        count += 1
                        if count % 10000 == 0:
                            logger.info(f'  {count} files scanned ...')
    finally:
        if symlink_f:
            symlink_f.close()

    logger.info(f'Scan complete: {count} regular files written to {files_csv}')
    if symlinks_csv:
        logger.info(f'Symlinks: {symlink_count} written to {symlinks_csv}')


# ---------------------------------------------------------------------------
# Phase 2 – check against r2d2 API
# ---------------------------------------------------------------------------

def fetch_registered_indices(item: str) -> set:
    """Return the set of all data_index values currently registered in r2d2 for item."""
    import r2d2
    logger.info(f'  Fetching registered indices for item={item} ...')
    results = r2d2.search(item=item, include_item_index=True)
    index_key = f'{item}_index'
    indices = {r[index_key] for r in results if index_key in r}
    logger.info(f'    -> {len(indices)} registered entries')
    return indices


def check_orphans(files_csv: str, output_csv: str):
    """Compare files_csv against r2d2 and write orphaned files to output_csv."""
    with open(files_csv, newline='') as f:
        rows = list(csv.DictReader(f))
    logger.info(f'Loaded {len(rows)} files from {files_csv}')

    # One API call per item type to bulk-fetch all registered indices
    items_present = sorted({r['item'] for r in rows})
    registered = {item: fetch_registered_indices(item) for item in items_present}

    orphans = []
    for row in rows:
        item = row['item']
        idx = int(row['index'])
        if idx not in registered.get(item, set()):
            size_bytes = int(row['size_bytes'])
            orphans.append({
                'filepath':   row['filepath'],
                'item':       item,
                'date':       row['date'],
                'index':      idx,
                'extension':  row['extension'],
                'size_bytes': size_bytes,
                'size_mb':    round(size_bytes / 1e6, 3),
                'size_gb':    round(size_bytes / 1e9, 6),
            })

    total_bytes = sum(r['size_bytes'] for r in orphans)
    logger.info(
        f'Found {len(orphans)} orphaned files '
        f'({total_bytes / 1e12:.3f} TB) out of {len(rows)} total.'
    )

    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=ORPHAN_FIELDNAMES)
        writer.writeheader()
        writer.writerows(orphans)

    logger.info(f'Orphan report written to: {output_csv}')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Find unregistered (orphaned) files in an r2d2 local data store.'
    )
    parser.add_argument('--scan', action='store_true',
                        help='Phase 1: walk the filesystem and write a files CSV.')
    parser.add_argument('--check', action='store_true',
                        help='Phase 2: check files CSV against r2d2 API and write orphans CSV.')
    parser.add_argument('--basedir',
                        help='Root directory of the data store (required for --scan).')
    parser.add_argument('--data-store',
                        help='Name of the data store directory (required for --scan).')
    parser.add_argument('--files-csv', default='files.csv',
                        help='Files CSV written by --scan / read by --check. Default: files.csv')
    parser.add_argument('--symlinks-csv', default=None,
                        help='CSV to write all symlinks (live and dangling) found during --scan. Optional.')
    parser.add_argument('--output', default='orphans.csv',
                        help='Orphans output CSV (used by --check). Default: orphans.csv')
    args = parser.parse_args()

    if not args.scan and not args.check:
        parser.error('Specify at least one of --scan or --check.')

    if args.scan:
        if not args.basedir or not args.data_store:
            parser.error('--basedir and --data-store are required when using --scan.')
        basedir = os.path.expanduser(args.basedir)
        if not os.path.isdir(basedir):
            logger.error(f'basedir does not exist: {basedir}')
            sys.exit(1)
        try:
            scan_data_store(basedir, args.data_store, args.files_csv, args.symlinks_csv)
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)

    if args.check:
        if not os.path.isfile(args.files_csv):
            logger.error(f'Files CSV not found: {args.files_csv}  (run --scan first)')
            sys.exit(1)
        check_orphans(args.files_csv, args.output)


if __name__ == '__main__':
    main()
