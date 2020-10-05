import sys
import setuptools
from cx_Freeze import setup, Executable

"""
Notes:
__init__.py file created in mpl_toolkit
Use cx_freeze==6.1. 6.2 produces errors.
"""

build_exe_options = {
    # "packages": ["pyproj", "scipy"],
    "packages": ["pyproj", "scipy", "pkg_resources", "os", "pandas", "numpy", "idna", "branca", "jinja2", "matplotlib"],
    # build_exe_options = {"packages": [
    #     "attr",
    #     "branca",
    #     "cartopy",
    #     "fiona",
    #     "folium",
    #     "geomag",
    #     "geopandas",
    #     "gpxpy",
    #     "idna",
    #     "jinja2",
    #     "js2py",
    #     "keyboard",
    #     "matplotlib",
    #     "natsort",
    #     "numpy",
    #     "pandas",
    #     "plotly",
    #     "pyproj",
    #     # "pyqt5",
    #     "pyqtgraph",
    #     "pyunpack",
    #     "scipy",
    #     "shapely",
    #     "simplekml",
    #     "utm"
    # ],
    "includes": ["pyqtgraph.ThreadsafeTimer", "tkinter"],
    # "includes": ["pyqtgraph.ThreadsafeTimer"],
    "excludes": ["matplotlib.tests", "numpy.random._examples", "scipy.spatial.cKDTree"],
    "include_files": ["src/qt_ui", "venv/Lib/site-packages/PyQt5"],  # Copy the folders
    # "optimize": 2,
    # "include_msvcr": True,
    # "add_to_path": True,
}

# GUI applications require a different base on Windows (the default is for a console application).
base = None

# if sys.platform == "win32":  # Comment out for debugging
#     base = "Win32GUI"

setup(name="PEMPro",
      version="0.11.0",
      description="Crone Processing Suite.",
      options={"build_exe": build_exe_options},
      executables=[Executable("run.py",
                              base=base,
                              icon='conder.ico',
                              targetName='PEMPro',
                              # shortcutName='PEMPro'
                              ),
                   ])
