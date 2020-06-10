import os
import sys

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

src_dir = os.path.join(application_path, "src")

print('src directory: '+src_dir)

# Needed to keep run.py outside of src directory
# os.chdir(src_dir)
# sys.path.append(src_dir)

# from src.qt_py.main_window import MainWindow
from src.qt_py.pem_editor import PEMEditor
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer


def main():
    # TODO Make dedicated Application class
    app = QApplication(sys.argv)
    window = PEMEditor()
    window.show()
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()