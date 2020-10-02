import sys
from cx_Freeze import setup, Executable

"""
Notes:
__init__.py file created in mpl_toolkit
"""

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["os", "pyproj", "scipy"],
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
                     "excludes": ["matplotlib.tests", "numpy.random._examples", "scipy.spatial.cKDTree"],
                     "include_files": ["src/qt_ui", "venv/Lib/site-packages/PyQt5"]}  # Copy the folders

# GUI applications require a different base on Windows (the default is for a console application).
base = None
# if sys.platform == "win32":  # Comment out for debugging
#     base = "Win32GUI"

setup(name="PEMPro",
      version="0.11.0",
      description="Crone Processing Suite.",
      options={"build_exe": build_exe_options},
      executables=[Executable("run.py", base=base, icon='conder.ico')])
