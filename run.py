import os
import sys

src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
print('src directory: '+src_dir)

# Needed to keep run.py outside of src directory
os.chdir(src_dir)
sys.path.append(src_dir)

from qt_py.main_window import MainWindow
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QTimer

def main():
    # TODO Make dedicated Application class
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()