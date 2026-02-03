import os
from datetime import datetime, timedelta

import logging

for name in ["r2d2", "r2d2.r2d2", "r2d2.r2d2_client"]:
    logging.getLogger(name).disabled = True


from r2d2 import r2d2

# Config - should be a yaml
experiment = 'ca343c'
r2d2_db = '/css/jcsda/s2127/r2d2-experiments-nccs/'
data_store = 'r2d2-experiments-nccs'

start_date_str = '20230803T210000Z'
end_date_str   = '20230901T030000Z'
date_format = '%Y%m%dT%H%M%SZ'

members_to_keep = {-9999, 0, 1}

items = ['forecast', 'analysis', 'feedback']

target_file_types = {
    'forecast': ['bkg'],
    'analysis': ['bkg'],
}

DRY_RUN = False  # set to False to actually delete


# functions
def get_index_key(item):
    return {
        'forecast': 'forecast_index',
        'analysis': 'analysis_index',
        'feedback': 'feedback_index'
    }[item]

def get_time_key(item):
    return {
        'forecast': 'date',
        'analysis': 'date',
        'feedback': 'window_start'
    }[item]

def safe_int_member(val):
    try:
        return int(val)
    except Exception:
        return None

def build_file_path(item, record):
    idx = record.get(get_index_key(item))
    t = record.get(get_time_key(item))
    ext = record.get('file_extension', 'nc4')
    if idx is None or t is None:
        return None
    return os.path.join(r2d2_db, item, t, f"{idx}.{ext}")

def delete_file(item, record, path):
    if DRY_RUN:
        print(f"DRY_RUN would delete: {path}")
        return
    try:
        if item == 'forecast':
            r2d2.delete(
                item='forecast',
                experiment=record['experiment'],
                file_type='bkg', #record['file_type'], #this will not remove the restarts, this is in another script
                step=record['step'],
                member=str(record['member']),
                date=record['date'],
                model=record['model'],
                resolution=record['resolution'],
                data_store=data_store,
                file_extension=record.get('file_extension', 'nc')
            )

        elif item == 'analysis':
            r2d2.delete(
                item='analysis',
                experiment=record['experiment'],
                file_type='bkg',#record['file_type'],
                member=str(record['member']),
                date=record['date'],
                model=record['model'],
                resolution=record['resolution'],
                data_store=data_store,
                file_extension=record.get('file_extension', 'nc')
            )

        elif item == 'feedback':
            r2d2.delete(
                item='feedback',
                experiment=record['experiment'],
                observation_type=record['observation_type'],
                member=str(record['member']),
                window_start=record['window_start'],
                window_length=record['window_length'],
                data_store=data_store,
                file_extension=record.get('file_extension', 'nc4')
            )

        print(f"Deleted: {path}")

    except Exception as e:
        print(f"Failed to delete: {path} ({e})")

# main
start_date = datetime.strptime(start_date_str, date_format)
end_date   = datetime.strptime(end_date_str, date_format)

current_time = start_date
while current_time <= end_date:
    t_str = current_time.strftime(date_format)

    for item in items:
        print(current_time, item)
        time_key = get_time_key(item)

        try:
            if item in ('forecast', 'analysis'):
                results = []
                for ft in target_file_types.get(item, []):
                    results.extend(
                        r2d2.search(
                            item=item,
                            experiment=experiment,
                            file_type=ft,
                            **{time_key: t_str},
                            include_item_index=True
                        )
                    )
            else:
                # feedback
                results = r2d2.search(
                    item=item,
                    experiment=experiment,
                    **{time_key: t_str},
                    include_item_index=True
                )
        except Exception as e:
            print(f"Search error: item={item} time={t_str}: {e}")
            continue

        for record in results:
            m = safe_int_member(record.get('member'))
            if m is None:
                # safer to skip unknown member rather than delete
                continue

            # Keep only -9999 and 0; delete files for all other members
            if m in members_to_keep:
                continue

            fpath = build_file_path(item, record)
            if not fpath:
                continue

            if os.path.exists(fpath):
                print(f"Deleting file {record}")
                print(f"Path before calling delete fct: {fpath}")
                delete_file(item, record, fpath)

    current_time += timedelta(hours=1)
