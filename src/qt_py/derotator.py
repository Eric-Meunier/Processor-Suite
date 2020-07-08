import sys
import os
import keyboard
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QMainWindow, QApplication, QMessageBox, QRadioButton, QGridLayout,
                             QLabel, QLineEdit, QDialogButtonBox, QAbstractItemView)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    icons_path = 'icons'
    derotatorCreatorFile = 'qt_ui\\derotator.ui'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")
    derotatorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\derotator.ui')

# Load Qt ui file into a class
Ui_Derotator, QtBaseClass = uic.loadUiType(derotatorCreatorFile)


class Derotator(QMainWindow, Ui_Derotator):

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        self.parent = parent
        self.pem_files = []

        self.setWindowTitle('XY De-rotation')
        self.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, 'derotate.png')))

        self.message = QMessageBox()

        self.button_box.accepted.connect(self.rotate)
        self.button_box.rejected.connect(self.close)

        int_validator = QtGui.QIntValidator()
        self.soa_edit.setValidator(int_validator)

    def open(self, pem_files):
        if not isinstance(pem_files, list):
            pem_files = [pem_files]

        for file in pem_files:
            if all([file.is_borehole(), 'X' in file.get_components(), 'Y' in file.get_components()]):
                self.pem_files.append(file)

        if not self.pem_files:
            self.message.information(self, 'No eligible files found',
                                     'Only accepts borehole files with X and Y component data.')
            return

        else:
            for pem_file in self.pem_files:
                if pem_file.is_rotated():
                    response = self.message.question(self, 'File already de-rotated',
                                                     f"{pem_file.filename} is already de-rotated. " +
                                                     'Do you wish to de-rotate again?',
                                                     self.message.Yes | self.message.No)
                    if response == self.message.No:
                        continue
                self.file_list.addItem(pem_file.filename)
            self.show()

    def rotate(self):
        if self.acc_btn.isChecked():
            method = 'acc'
        elif self.mag_btn.isChecked():
            method = 'mag'
        else:
            method = 'pp'
        soa = int(self.soa_edit.text())

        for pem_file in self.pem_files:
            pem_file = pem_file.rotate(method=method, soa=soa)


def main():
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)
    mw = Derotator()

    pg = PEMGetter()
    pem_files = pg.get_pems(client='Raglan', number=10)
    mw.open(pem_files)

    app.exec_()


if __name__ == '__main__':
    main()