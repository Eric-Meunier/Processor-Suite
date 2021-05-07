import sys
import os
from pathlib import Path
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog,
                             QAbstractScrollArea, QTableWidgetItem, QAction, QMenu, QProgressBar, QGridLayout,
                             QInputDialog, QHeaderView, QTableWidget, QErrorMessage, QDialogButtonBox, QVBoxLayout,
                             QLabel, QLineEdit, QPushButton)
from src.pem.pem_plotter import GeneralMap

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).absolute().parents[1]
reportGeneratorDesignerFile = application_path.joinpath('ui\\report_generator.ui')
icons_path = application_path.joinpath("ui\\icons")

# Load Qt ui file into a class
Ui_ReportGenerator, QtBaseClass = uic.loadUiType(reportGeneratorDesignerFile)


class ReportGenerator(QMainWindow, Ui_ReportGenerator):

    def __init__(self):
        super().__init__()
        self.setupUi(self)


if __name__ == '__main__':
    from src.pem.pem_getter import PEMGetter
    app = QApplication(sys.argv)

    pg = PEMGetter()
    pem_files = pg.get_pems()
    # w = ReportGenerator()
    # w.show()

    app.exec_()