import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pem.pem_editor import PEMFileEditor
from qt_py.pem_file_widget import PEMFileWidget


class FileBrowser(QTabWidget):
    def __init__(self, parent=None):
        super(FileBrowser, self).__init__(parent)
        # self.setWindowTitle("tab demo")

        self.editors = []
        self.widgets = []
        self.active_editor = None

    def open_file(self, file_name):
        # TODO Logic for different file types

        self.editors.append(PEMFileEditor())
        self.editors[-1].open_file(file_name)
        self.active_editor = self.editors[-1]

        self.widgets.append( PEMFileWidget() )
        self.widgets[-1].open_file(file_name)
        self.addTab(self.widgets[-1], file_name)


def main():
    app = QApplication(sys.argv)
    ex = FileBrowser()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()