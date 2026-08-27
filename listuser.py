import csv, os, pwd, sys
from collections import defaultdict

csvfile = sys.argv[1] if len(sys.argv) > 1 else 'orphans_nccs.csv'
by_owner = defaultdict(lambda: {'count': 0, 'bytes': 0})
uid_cache = {}

with open(csvfile) as f:
    for row in csv.DictReader(f):
        try:
            uid = os.stat(row['filepath'], follow_symlinks=False).st_uid
            owner = uid_cache.setdefault(uid, pwd.getpwuid(uid).pw_name)
        except (OSError, KeyError):
            owner = 'unknown'
        by_owner[owner]['count'] += 1
        by_owner[owner]['bytes'] += int(row['size_bytes'])

print(f"{'Owner':<30}  {'Files':>8}  {'Size (GB)':>12}")
print('-' * 56)
for owner, d in sorted(by_owner.items(), key=lambda x: -x[1]['bytes']):
    print(f"{owner:<30}  {d['count']:>8}  {d['bytes']/1e9:>12.3f}")
