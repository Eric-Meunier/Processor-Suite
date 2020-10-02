import sys
import os
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QDesktopWidget, QMessageBox, QFileDialog,
                             QAbstractScrollArea, QTableWidgetItem, QAction, QMenu, QProgressBar, QGridLayout,
                             QInputDialog, QHeaderView, QTableWidget, QErrorMessage, QDialogButtonBox, QVBoxLayout,
                             QLabel, QLineEdit, QPushButton)
from src.pem.pem_plotter import GeneralMap

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = os.path.dirname(sys.executable)
    reportGeneratorDesignerFile = 'qt_ui\\report_generator.ui'
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    reportGeneratorDesignerFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\report_generator.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

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