"""Find unregistered (orphaned) files in an r2d2 local data store.

Strategy:
  1. Walk the data store directory and list all files.
  2. Parse each file path to extract the item type, date, and database index.
  3. Query r2d2 data_register to check if each index is registered.
  4. Write unregistered files and their sizes to a CSV report.

Requires direct database access (server-side or same MYSQL_* env vars as the server).

Usage:
    # Discover data store (nccs-gmao partition):
    python find_unregistered_files.py \
        --basedir /discover/nobackup/projects/gmao/swell \
        --data-store r2d2-experiments-nccs-gmao \
        --output unregistered_gmao.csv

    # NCCS data store:
    python find_unregistered_files.py \
        --basedir /css/jcsda/s2127 \
        --data-store r2d2-experiments-nccs \
        --output unregistered_nccs.csv

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

# Data items that write files to disk
DATA_ITEMS = {
    'analysis', 'bias_correction', 'diagnostic',
    'feedback', 'forecast', 'media', 'observation'
}


def get_data_store_index(cursor, data_store_name: str) -> int:
    cursor.execute('SELECT data_store_index FROM data_store WHERE name = %s', (data_store_name,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f'Data store "{data_store_name}" not found in the database.')
    return row['data_store_index']


def get_item_index(cursor, item_name: str) -> int:
    cursor.execute('SELECT item_index FROM item WHERE name = %s', (item_name,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f'Item "{item_name}" not found in the database.')
    return row['item_index']


def is_registered(cursor, item_index: int, data_index: int, data_store_index: int) -> bool:
    cursor.execute(
        'SELECT 1 FROM data_register '
        'WHERE item_index = %s AND data_index = %s AND data_store_index = %s '
        'LIMIT 1',
        (item_index, data_index, data_store_index)
    )
    return cursor.fetchone() is not None


def walk_data_store(basedir: str, data_store_name: str):
    """Yield (filepath, item, date, index_str) for every leaf file under the data store root.

    Expected directory structure:
        <basedir>/<data_store_name>/<item>/<date>/<index>[.<ext>]
    """
    root = os.path.join(basedir, data_store_name)
    if not os.path.isdir(root):
        raise FileNotFoundError(f'Data store directory not found: {root}')

    for item in os.scandir(root):
        if not item.is_dir() or item.name not in DATA_ITEMS:
            continue
        item_name = item.name

        for date_entry in os.scandir(item.path):
            if not date_entry.is_dir():
                continue
            date_str = date_entry.name

            for file_entry in os.scandir(date_entry.path):
                if not file_entry.is_file():
                    continue
                # Index is the filename without extension
                index_str = os.path.splitext(file_entry.name)[0]
                yield file_entry.path, item_name, date_str, index_str


def get_db_cursor():
    """Return a dict-cursor connected to the r2d2 database using the same env vars as the server."""
    import mysql.connector
    connect_args = {
        'user':     os.environ.get('MYSQL_USER', 'r2d2'),
        'host':     os.environ.get('MYSQL_HOST', 'localhost'),
        'database': os.environ.get('MYSQL_DATABASE', 'r2d2'),
        'port':     int(os.environ.get('MYSQL_PORT', 3306)),
    }
    if 'MYSQL_PASSWORD' in os.environ:
        connect_args['password'] = os.environ['MYSQL_PASSWORD']
    conn = mysql.connector.connect(**connect_args)
    return conn, conn.cursor(dictionary=True)


def find_unregistered(basedir: str, data_store_name: str, output_csv: str):
    logger.info(f'Connecting to database ...')
    conn, cursor = get_db_cursor()

    logger.info(f'Looking up data store: {data_store_name}')
    data_store_index = get_data_store_index(cursor, data_store_name)

    # Pre-load all item name -> item_index mappings for DATA_ITEMS
    item_index_cache = {}
    for item_name in DATA_ITEMS:
        try:
            item_index_cache[item_name] = get_item_index(cursor, item_name)
        except ValueError:
            logger.warning(f'Item "{item_name}" not found in DB — skipping.')

    logger.info(f'Walking filesystem: {os.path.join(basedir, data_store_name)}')

    unregistered = []
    total_files = 0
    total_unregistered = 0

    for filepath, item_name, date_str, index_str in walk_data_store(basedir, data_store_name):
        total_files += 1

        if item_name not in item_index_cache:
            continue

        try:
            data_index = int(index_str)
        except ValueError:
            logger.warning(f'Could not parse index from filename: {filepath}')
            continue

        if not is_registered(cursor, item_index_cache[item_name], data_index, data_store_index):
            size_bytes = os.path.getsize(filepath)
            unregistered.append({
                'filepath':   filepath,
                'item':       item_name,
                'date':       date_str,
                'index':      data_index,
                'size_mb':    round(size_bytes / 1e6, 3),
            })
            total_unregistered += 1

        if total_files % 10000 == 0:
            logger.info(f'  Scanned {total_files} files, {total_unregistered} unregistered so far ...')

    cursor.close()
    conn.close()

    # Summary
    total_orphan_bytes = sum(r['size_bytes'] for r in unregistered)
    logger.info(f'Scan complete: {total_files} total files, '
                f'{total_unregistered} unregistered '
                f'({total_orphan_bytes / 1e12:.3f} TB orphaned).')

    # Write CSV
    fieldnames = ['filepath', 'item', 'date', 'index', 'size_bytes', 'size_mb', 'size_gb']
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unregistered)

    logger.info(f'Report written to: {output_csv}')


def main():
    parser = argparse.ArgumentParser(
        description='Find unregistered (orphaned) files in an r2d2 local data store.'
    )
    parser.add_argument(
        '--basedir', required=True,
        help='Root directory of the data store (e.g. /css/jcsda/s2127)'
    )
    parser.add_argument(
        '--data-store', required=True,
        help='Name of the data store (e.g. r2d2-experiments-nccs)'
    )
    parser.add_argument(
        '--output', default='unregistered_files.csv',
        help='Path to output CSV file (default: unregistered_files.csv)'
    )
    args = parser.parse_args()

    basedir = os.path.expanduser(args.basedir)
    if not os.path.isdir(basedir):
        logger.error(f'basedir does not exist: {basedir}')
        sys.exit(1)

    try:
        find_unregistered(
            basedir=basedir,
            data_store_name=args.data_store,
            output_csv=args.output,
        )
    except (ValueError, FileNotFoundError) as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
