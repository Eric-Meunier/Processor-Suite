import os
from pathlib import Path

# Create the AppData folder used to save temporary data and settings
app_data_dir = Path(os.getenv('APPDATA')).joinpath("PEMPro")
app_data_dir.mkdir(exist_ok=True)

__version__ = '0.12.1'
