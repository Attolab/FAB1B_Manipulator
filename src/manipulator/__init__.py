from pathlib import Path


NICE_NAME = 'XY Manipulator'
module_name = 'manipulator'
klass_name = 'Manipulator'


# ############

try:
    with open(str(Path(__file__).parent.joinpath('VERSION')), 'r') as fvers:
        __version__ = fvers.read().strip()


except Exception as e:
    print(str(e))
