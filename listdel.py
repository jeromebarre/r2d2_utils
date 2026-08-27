import csv, os, pwd

csvfile = 'orphans_nccs.csv'
target_owner = 'jbarre'
uid_cache = {}

with open(csvfile) as f:
    for row in csv.DictReader(f):
        fp = row['filepath']
        try:
            uid = os.stat(fp, follow_symlinks=False).st_uid
            owner = uid_cache.setdefault(uid, pwd.getpwuid(uid).pw_name)
        except (OSError, KeyError):
            owner = 'unknown'
        if owner == target_owner:
            print(fp)
