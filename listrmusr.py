import csv, os, pwd

csvfile = 'orphans_nccs.csv'
target_owner = 'jbarre'
uid_cache = {}
removed = 0
errors = 0

with open(csvfile) as f:
    for row in csv.DictReader(f):
        fp = row['filepath']
        try:
            uid = os.stat(fp, follow_symlinks=False).st_uid
            owner = uid_cache.setdefault(uid, pwd.getpwuid(uid).pw_name)
        except (OSError, KeyError):
            owner = 'unknown'
        if owner == target_owner:
            try:
                os.remove(fp)
                removed += 1
            except OSError as e:
                print(f'ERROR: {fp}: {e}')
                errors += 1

print(f'Done: {removed} files removed, {errors} errors.')
