import r2d2


list_exp = [
        '4d742a',
        '236be4',
        '46411e'
        ]

for exp in list_exp:
    r2d2.deregister(item='experiment', name=exp, ignore_lifetime=True)
