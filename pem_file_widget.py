from PyQt5.QtWidgets import QMainWindow, QApplication, QAction, QFileDialog, QWidget
from PyQt5 import uic
from pem_editor import PEMFileEditor

qtCreatorFile = "pem_file_form.ui"  # Enter file here.
Ui_PEMFileWidget, QtBaseClass = uic.loadUiType(qtCreatorFile)


class PEMFileWidget(QWidget, Ui_PEMFileWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
        Ui_PEMFileWidget.__init__(self)
        self.setupUi(self)
        self.editor = PEMFileEditor()

    def open_file(self, file_name):
        self.editor.open_file(file_name)
        self.label.setText(file_name)