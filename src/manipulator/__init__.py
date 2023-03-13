from pathlib import Path


NICE_NAME = 'MyExtension'
module_name = 'extension'
klass_name = 'MyExtension'


# ############

try:
    with open(str(Path(__file__).parent.joinpath('VERSION')), 'r') as fvers:
        __version__ = fvers.read().strip()


except Exception as e:
    print(str(e))
