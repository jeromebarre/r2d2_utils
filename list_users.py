import r2d2

data_store = 'r2d2-experiments-nccs'
hostname = 'discover-mil-gnu'

# Step 1 — get the data_hub for this data store
ds = r2d2.get(item='data_store', name=data_store)
data_hub = ds['data_hub']  # e.g. 'nccs-gmao'

# Step 2 — find compute hosts linked to that data hub
# (no direct API — use what you know, e.g. 'discover-gmao-intel')
compute_hosts = r2d2.search(item='compute_host', hostname=hostname, compiler='gnu')

# Step 3 — search experiments for each compute host and collect unique users
users = set()
for ch in compute_hosts:
    experiments = r2d2.search(item='experiment', compute_host=ch['name'])
    for exp in experiments:
        users.add(exp['user'])

print(users)
