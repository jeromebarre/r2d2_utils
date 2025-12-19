from datetime import datetime
import r2d2
import os
import csv


def get_experiment_file_info(model, experiment, item):
    """Return count and total size (in GB) of files for a given experiment and item."""
    r2d2_db = '/css/jcsda/s2127/r2d2-experiments-nccs/'

    if item == "feedback":
        files = r2d2.search(experiment=experiment, item=item, include_item_index=True)
    else:
        files = r2d2.search(model=model, experiment=experiment, item=item, include_item_index=True)

    total_size = 0
    for f in files:
        wstart = f.get('date')
        ext = f.get('file_extension', 'nc4')
        index = str(f.get(f"{item}_index"))
        if wstart is None:
            continue
        if index is None:
            continue
        path = os.path.join(r2d2_db, item, wstart, f"{index}.{ext}")
        if path and os.path.exists(path):
            total_size += os.path.getsize(path)
    return len(files), total_size / 1e9  # convert to GB


def collect_experiments_for_user(user, csv_rows):
    """Collect experiment info for a specific user and append to csv_rows list."""
    experiments = r2d2.search(user=user, item='experiment')

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
            f"{fc_size:.2f}",
            an_count,
            f"{an_size:.2f}",
            fb_count,
            f"{fb_size:.2f}"
        ])
        print(csv_rows)


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

list_user = ['barre']

csv_rows = []

# Header row
csv_rows.append([
    "User", "Experiment Name", "Lifetime", "Members",
    "FC Files", "FC Size (GB)",
    "AN Files", "AN Size (GB)",
    "FB Files", "FB Size (GB)"
])

# Collect all users' experiments
for user in list_user:
    collect_experiments_for_user(user, csv_rows)

# Write to CSV
output_file = "r2d2_experiments_all_users.csv"
with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(csv_rows)

print(f"\nCSV file written to: {output_file}\n")

