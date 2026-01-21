from datetime import datetime
from r2d2 import r2d2  # Adjust import as needed

# Configuration
experiment = 'dfa369'
data_store = 'r2d2-experiments-nccs'
model = 'geos_cf'
resolution = 'c360'
member = '-9999'
step = 'PT6H'
file_extension = 'nc'

# Date range (inclusive)
start_date = datetime.strptime('20230805T000000Z', '%Y%m%dT%H%M%SZ')
end_date   = datetime.strptime('20230825T000000Z', '%Y%m%dT%H%M%SZ')

# List of file types to delete
file_types = [
    'achem_internal', 'aiau_import', 'cabc_internal', 
    'cabr_internal', 'caoc_internal', 'catch_internal', 'du_internal', 
    'fvcore_internal', 'geoschemchem_import', 'geoschemchem_internal', 
    'gocart_import', 'gocart_internal', 'gwd_import', 'hemco_import', 
    'hemco_internal', 'irrad_internal', 'lake_internal', 'landice_internal', 
    'moist_import', 'moist_internal', 'ni_internal', 'openwater_internal', 
    'pchem_internal', 'saltwater_import', 'seaicethermo_internal', 
    'solar_internal', 'ss_internal', 'su_internal', 'surf_import', 
    'tr_import', 'tr_internal', 'turb_import', 'turb_internal'
]

# Helper: Parse R2D2 datetime string
def parse_r2d2_date(date_str):
    return datetime.strptime(date_str, '%Y%m%dT%H%M%SZ')

# Process each file type
for file_type in file_types:
    print(f"Searching for file_type: {file_type}")
    results = r2d2.search(item='forecast', experiment=experiment, file_type=file_type)
    
    for record in results:
        record_date = parse_r2d2_date(record['date'])
        if start_date <= record_date <= end_date:
            print(f"Deleting file with date: {record['date']} (file_type: {file_type})")
            r2d2.delete(
                item='forecast',
                experiment=experiment,
                file_type=file_type,
                step=step,
                member=str(record.get('member', member)),
                date=record['date'],
                model=record.get('model', model),
                resolution=record.get('resolution', resolution),
                data_store=data_store,
                file_extension=record.get('file_extension', file_extension)
            )
