import os
import time
from pathlib import Path

# Create the AppData folder used to save temporary data and settings
app_data_dir = Path(os.getenv('APPDATA')).joinpath("PEMPro")
app_data_dir.mkdir(exist_ok=True)

app_temp_dir = Path(os.getenv('APPDATA')).joinpath("PEMPro/temp")
app_temp_dir.mkdir(exist_ok=True)

samples_folder = Path(__file__).parents[1].joinpath("sample_files")


def timeit(method):
    """
    Decorator to measure execution time of a method.
    :param method: function
    """
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print(f"{method.__name__} {(te - ts):.3f} s")
        return result
    return timed


__version__ = '0.12.5'
