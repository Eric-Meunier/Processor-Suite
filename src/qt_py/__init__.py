import os
import sys
from PySide2.QtGui import QPixmap, QIcon
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


def get_icon(filepath):
    ext = filepath.suffix.lower()
    if ext in ['.xls', '.xlsx', '.csv']:
        icon_pix = QPixmap(str(icons_path.joinpath('excel_file.png')))
        if not (icons_path.joinpath('excel_file.png').exists()):
            print(f"{icons_path.joinpath('excel_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.rtf', '.docx', '.doc']:
        icon_pix = QPixmap(str(icons_path.joinpath('word_file.png')))
        if not (icons_path.joinpath('word_file.png').exists()):
            print(f"{icons_path.joinpath('word_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.log', '.txt', '.xyz', '.seg', '.dad']:
        icon_pix = QPixmap(str(icons_path.joinpath('txt_file.png')))
        if not (icons_path.joinpath('txt_file.png').exists()):
            print(f"{icons_path.joinpath('txt_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.pem']:
        icon_pix = QPixmap(str(icons_path.joinpath('crone_logo.png')))
        if not (icons_path.joinpath('crone_logo.png').exists()):
            print(f"{icons_path.joinpath('crone_logo.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.dmp', '.dmp2', '.dmp3', '.dmp4']:
        icon_pix = QPixmap(str(icons_path.joinpath('dmp.png')))
        if not (icons_path.joinpath('dmp.png').exists()):
            print(f"{icons_path.joinpath('dmp.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.gpx', '.gdb']:
        icon_pix = QPixmap(str(icons_path.joinpath('garmin_file.png')))
        if not (icons_path.joinpath('garmin_file.png').exists()):
            print(f"{icons_path.joinpath('garmin_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.ssf']:
        icon_pix = QPixmap(str(icons_path.joinpath('ssf_file.png')))
        if not (icons_path.joinpath('ssf_file.png').exists()):
            print(f"{icons_path.joinpath('ssf_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    elif ext in ['.cor']:
        icon_pix = QPixmap(str(icons_path.joinpath('cor_file.png')))
        if not (icons_path.joinpath('cor_file.png').exists()):
            print(f"{icons_path.joinpath('cor_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    else:
        icon_pix = QPixmap(str(icons_path.joinpath('none_file.png')))
        if not (icons_path.joinpath('none_file.png').exists()):
            print(f"{icons_path.joinpath('none_file.png')} does not exist.")
        icon = QIcon(icon_pix)
    return icon


def clear_table(table):
    """
    Clear a given table
    """
    table.blockSignals(True)
    while table.rowCount() > 0:
        table.removeRow(0)
    table.blockSignals(False)
