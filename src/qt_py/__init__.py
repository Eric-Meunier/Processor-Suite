import os
import sys
from pathlib import Path


# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).absolute().parents[1]  # src folder path

icons_path = application_path.joinpath("ui\\icons")

# Create the AppData folder used to save temporary data and settings
app_data_dir = Path(os.getenv('APPDATA')).joinpath("PEMPro")
app_data_dir.mkdir(exist_ok=True)
