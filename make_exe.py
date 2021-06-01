from src.qt_py.pem_hub import __version__
import os

spec_file = r"run_pempro.spec"

"""
Notes:
-To solve "OSError: could not find or load spatialindex_c.dll": pip install osmnx (but must have matplotlib==3.3.2, which has the defaultParams error), or pip uninstall rtree.
-To solve "NameError: name 'defaultParams' is not defined": pip install matplotlib==3.2.2 (which will be incompatible with osmnx).
"""


def make_spec(spec_file):
    print(f"Creating .spec file for version {__version__}")
    with open(spec_file, "w+") as file:
        file.write(r'''
# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files # this is very helpful

sys.setrecursionlimit(5000)
block_cipher = None
options = []

paths = [
    sys.prefix,  # venv path
]

binaries = [

]

hidden_imports = [
    'fiona._shim',  # Required
    'fiona.schema',  # Required
    'PySide2.QtXml'  # Required
]

a = Analysis(['run.py'],
             pathex=paths, # add all your paths
             binaries=binaries, # add the dlls you may need
             datas=collect_data_files('geopandas', subdir='datasets') +  # Required
                   [
                   (r'src\ui\*.ui','ui'), # Places all .ui files in a folder called 'qt_ui'
                   (r'src\ui\icons\*.png', r'ui/icons'),  # Places all icon files in a folder called 'icons'
                   (r'src\ui\icons\*.ico', r'ui/icons'),
                   (r'.mapbox', r'.'),
                   (r'venv\Lib\site-packages\geomag\WMM.COF', 'geomag'),  # Places a file used for magnetic declination calculation in a 'geomag' folder.
                   (r'venv\Lib\site-packages\plotly', 'plotly'),  # Required
                   ],
             hiddenimports=hidden_imports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          options,
          exclude_binaries=True,
          name='PEMPro',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          console=False, icon=r'src/ui/icons/conder.ico')
        ''')

        file.write(f"""
coll = COLLECT(exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PEMPro V{__version__}')
        """)


make_spec(spec_file)
# os.startfile(os.path.abspath(output))
os.system(f'cmd /k "pyinstaller --onedir --noconfirm {spec_file}"')
