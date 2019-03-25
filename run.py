from qt_py.main_window import MainWindow
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import sys


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