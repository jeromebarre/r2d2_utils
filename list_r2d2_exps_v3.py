from datetime import datetime
import r2d2
import os
import csv

# Select the compute host here
#compute_host = 'discover-mil-gnu'
compute_host = 'discover-gmao-intel'

R2D2_DB_ROOTS = {
    #'discover-mil-gnu':   '/css/jcsda/s2127/r2d2-experiments-nccs/',
    'discover-gmao-intel': '/discover/nobackup/projects/gmao/swell/r2d2-experiments-nccs-gmao/',
}
r2d2_db_root = R2D2_DB_ROOTS[compute_host]


# Some installations of r2d2 do not support the `include_item_index` search
# option, which is required to reconstruct on-disk file paths (and therefore
# file sizes). We detect support once at runtime and fall back to just
# counting files (without sizes) when it isn't available.
_supports_item_index = None


def _search_files(model, experiment, item):
    """Run r2d2.search for the given item, falling back to a plain search
    (no index) if the installed r2d2 version doesn't support include_item_index."""
    global _supports_item_index

    search_kwargs = {'experiment': experiment, 'item': item}
    if item != "feedback":
        search_kwargs['model'] = model

    if _supports_item_index is not False:
        try:
            files = r2d2.search(**search_kwargs, include_item_index=True)
            _supports_item_index = True
            return files, True
        except TypeError:
            _supports_item_index = False
            print("Warning: this r2d2 version does not support 'include_item_index'; "
                  "file sizes will be reported as N/A.")

    return r2d2.search(**search_kwargs), False


def get_experiment_file_info(model, experiment, item):
    """Return count and total size (in bytes) of files for a given experiment
    and item. Size is None if the installed r2d2 version doesn't support
    looking up item indexes (needed to locate files on disk)."""
    r2d2_db = r2d2_db_root

    files, has_index = _search_files(model, experiment, item)

    if not has_index:
        return len(files), None

    total_size = 0
    for f in files:
        wstart = f.get('date')
        ext = f.get('file_extension', 'nc4')
        index = f.get(f"{item}_index")
        if wstart is None:
            continue
        if index is None:
            continue
        path = os.path.join(r2d2_db, item, wstart, f"{index}.{ext}")
        #print(path)
        if path and os.path.exists(path):
            total_size += os.path.getsize(path)
            #print("####### size add: ", total_size)
    return len(files), total_size


def collect_experiments_for_user(user, csv_rows):
    """Collect experiment info for a specific user and append to csv_rows list."""
    experiments = r2d2.search(user=user, item='experiment', compute_host=compute_host)

    if not experiments:
        print(f"No experiments found for user '{user}'.")
        return

    for exp in experiments:
        name = exp.get('name', 'N/A')
        lifetime = exp.get('lifetime', 'N/A')
        yaml_text = exp.get('yaml_text') or ""

        # Extract number of members
        members = 'N/A'
        for line in yaml_text.splitlines():
            if 'members:' in line:
                try:
                    members = int(line.split(':')[-1].strip())
                except ValueError:
                    members = 'N/A'

        model = exp.get('model', None)

        # Get forecast, analysis, and feedback file counts/sizes
        fc_count, fc_size = get_experiment_file_info(model, name, 'forecast')
        an_count, an_size = get_experiment_file_info(model, name, 'analysis')
        fb_count, fb_size = get_experiment_file_info(model, name, 'feedback')

        csv_rows.append([
            user,
            name,
            lifetime,
            members,
            fc_count,
            f"{fc_size:.2f}" if fc_size is not None else "N/A",
            an_count,
            f"{an_size:.2f}" if an_size is not None else "N/A",
            fb_count,
            f"{fb_size:.2f}" if fb_size is not None else "N/A"
        ])
        #print(csv_rows)


# ------------------------------
# MAIN SCRIPT
# ------------------------------

#list_user = ['',
#    'anna.v.shlyaeva', 'ashley', 'barre', 'benr', 'bjung', 'cgas', 'csampson',
#    'dom.heinzeller', 'eric2', 'fabiolrdiniz', 'fabiolrdiniz2', 'fcvandenberghe',
#    'fgoktas', 'gthompsn', 'haydenlj', 'hebert', 'huishao', 'juliechang890059',
#    'luke', 'mabdiosk', 'mary.abdi', 'maryamao', 'ncrossette', 'nrt',
#    'role-r2d2-admin', 'stephen.herbener', 'test', 'tremolet', 'unknown',
#    'vahl', 'vandenb', 'weiwilliam1987'
#]

list_user = ['barre'] #['maryamao', 'dardag', 'vshah', 'barre', 'fgoktas', 'gmao-user']

# Collect all users' experiments
for user in list_user:
    csv_rows = []
    csv_rows.append([
        "User", "Experiment Name", "Lifetime", "Members",
        "FC Files", "FC Size",
        "AN Files", "AN Size",
        "FB Files", "FB Size"
    ])
    collect_experiments_for_user(user, csv_rows)

    # Write to CSV
    output_file = f"r2d2_experiments_{user}.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)

    print(f"\nCSV file written to: {output_file}\n")

