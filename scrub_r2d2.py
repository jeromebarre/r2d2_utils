import r2d2


list_exp = [
        '684e02',
        ]

for exp in list_exp:
    r2d2.deregister(item='experiment', name=exp, ignore_lifetime=True)
