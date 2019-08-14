import os
import sys
import logging
from src.con_file.confile_modder import Conder
from src.damp.db_plot import DBPlot
from src.pem.new_pem_editor import PEMEditorWindow
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem, QMenuBar, QAction, QMenu)
from PyQt5 import (QtCore, QtGui, uic)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

__version__ = '0.0.0'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

MW_CreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\new_main_window.ui')
Ui_MainWindow, QtBaseClass = uic.loadUiType(MW_CreatorFile)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.initUi()
        self.initApps()
        self.initActions()

    def initUi(self):
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())
            self.show()

        self.setupUi(self)  # Init for the .UI file
        # layout = QGridLayout(self)
        # self.setLayout(layout)
        self.setAcceptDrops(True)
        self.setWindowTitle("PEMPro  v" + str(__version__))
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(os.path.dirname(application_path), "qt_ui\\icons\\crone_logo.ico")))
        self.setGeometry(500, 300, 1400, 900)
        center_window(self)

    def initApps(self):
        self.message = QMessageBox()
        self.dialog = QFileDialog()
        self.statusBar().showMessage('Ready')

        self.setCentralWidget(self.mdiArea)
        self.editor = None
        self.db_plot = None
        self.conder = None

    def initActions(self):
        self.menubar.hide()
        self.openFile = QAction("&Open File", self)
        self.openFile.setShortcut("Ctrl+O")
        self.openFile.setStatusTip('Open file')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.saveFiles = QAction("&Save Files", self)
        self.saveFiles.setShortcut("Ctrl+S")
        self.saveFiles.setStatusTip("Save all files")
        # self.saveFiles.triggered.connect(self.editor.save_all)

        self.clearFiles = QAction("&Clear Files", self)
        self.clearFiles.setShortcut("Ctrl+Del")
        self.clearFiles.setStatusTip("Clear all files")
        # self.clearFiles.triggered.connect(self.editor.clear_files)

        self.fileMenu = self.menubar.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.saveFiles)
        self.fileMenu.addAction(self.clearFiles)

        self.toolbar = self.addToolBar('')

        self.tile_view = QAction(
            QtGui.QIcon(os.path.join(os.path.dirname(application_path), "qt_ui\\icons\\windows_stack.png")), '&Tile View',
            self)
        self.tile_view.setShortcut('Ctrl+I')
        self.tile_view.triggered.connect(self.set_tile_view)

        self.show_pem_editor = QAction(
        QtGui.QIcon(os.path.join(os.path.dirname(application_path), "qt_ui\\icons\\plots2.png")), '&PEM Editor', self)
        self.show_pem_editor.triggered.connect(self.toggle_editor)

        self.show_db_plot = QAction(
        QtGui.QIcon(os.path.join(os.path.dirname(application_path), "qt_ui\\icons\\db_plot.png")), '&DB Plot', self)
        self.show_db_plot.triggered.connect(self.toggle_db_plot)

        self.show_conder = QAction(
        QtGui.QIcon(os.path.join(os.path.dirname(application_path), "qt_ui\\icons\\conder.png")), '&Conder', self)
        self.show_conder.triggered.connect(self.toggle_conder)

        self.toolbar.addAction(self.tile_view)
        self.toolbar.addAction(self.show_pem_editor)
        self.toolbar.addAction(self.show_db_plot)
        self.toolbar.addAction(self.show_conder)

    def set_tile_view(self):
        self.mdiArea.tileSubWindows()

    def closeIt(self):
        self.mdiArea.removeSubWindow(self.editor_subwindow)

    def toggle_editor(self):
        if self.editor is None:
            self.editor = PEMEditorWindow()
            self.editor_subwindow = self.mdiArea.addSubWindow(self.editor)
            self.editor.show()
            self.editor_subwindow.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
            self.mdiArea.tileSubWindows()
        else:
            if self.editor_subwindow.isHidden():
                self.editor.show()
                self.editor_subwindow.show()
                self.mdiArea.tileSubWindows()
            else:
                self.editor_subwindow.hide()
                self.mdiArea.tileSubWindows()

    def toggle_db_plot(self):
        if self.db_plot is None:
            self.db_plot = DBPlot()
            self.db_plot_subwindow = self.mdiArea.addSubWindow(self.db_plot)
            self.db_plot_subwindow.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
            self.db_plot.show()
            self.mdiArea.tileSubWindows()
        else:
            if self.db_plot_subwindow.isHidden():
                self.db_plot.show()
                self.db_plot_subwindow.show()
                self.mdiArea.tileSubWindows()
            else:
                self.db_plot_subwindow.hide()
                self.mdiArea.tileSubWindows()

    def toggle_conder(self):
        if self.conder is None:
            self.conder = Conder()
            self.conder_subwindow = self.mdiArea.addSubWindow(self.conder)
            self.conder_subwindow.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
            self.conder.show()
            self.mdiArea.tileSubWindows()
        else:
            if self.conder_subwindow.isHidden():
                self.conder.show()
                self.conder_subwindow.show()
                self.mdiArea.tileSubWindows()
            else:
                self.conder_subwindow.hide()
                self.mdiArea.tileSubWindows()

    def dragEnterEvent(self, e):
        urls = [url.toLocalFile().lower() for url in e.mimeData().urls()]
        accepted_extensions = ['pem', 'con', 'txt', 'log', 'rtf']

        def check_extension(urls):
            for url in urls:
                url_ext = url.split('.')[-1].lower()
                if url_ext in accepted_extensions:
                    continue
                else:
                    return False
            return True

        if check_extension(urls):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open_files(urls)

    def open_file_dialog(self):
        accepted_extensions = ['pem', 'con', 'txt', 'log', 'rtf']
        try:
            file = self.dialog.getOpenFileName(self, 'Open File')
            if file[0].split('.').lower() in accepted_extensions:
                self.open_files(file)
            else:
                self.message.information(None, 'Error', 'Invalid File Format')
                return
        except Exception as e:
            logging.warning(str(e))
            self.message.information(None, 'Error', str(e))
            pass

    def open_files(self, files):
        if not isinstance(files, list) and isinstance(files, str):
            files = [files]

        pem_files = [file for file in files if file.lower().endswith('pem')]
        con_files = [file for file in files if file.lower().endswith('con')]
        damp_files = [file for file in files if file.lower().endswith('txt') or file.lower().endswith('log')
                      or file.lower().endswith('rtf')]

        if len(pem_files) > 0:
            if self.editor is None:
                self.editor = PEMEditorWindow()
                self.editor_subwindow = self.mdiArea.addSubWindow(self.editor)
                self.editor_subwindow.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
                self.editor.show()
                self.mdiArea.tileSubWindows()
            try:
                self.editor.open_files(pem_files)
            except Exception as e:
                logging.warning(str(e))
                self.message.information(None, 'Error - Could not open selected PEM files', str(e))
                pass

        if len(damp_files) > 0:
            if self.db_plot is None:
                self.db_plot = DBPlot()
                self.db_plot_subwindow = self.mdiArea.addSubWindow(self.db_plot)
                self.db_plot_subwindow.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
                self.db_plot.show()
                self.mdiArea.tileSubWindows()
            try:
                self.db_plot.open_files(damp_files)
            except Exception as e:
                logging.warning(str(e))
                self.message.information(None, 'Error - Could not open selected damping box files', str(e))
                pass

        if len(con_files) > 0:
            if self.conder is None:
                self.conder = Conder()
                self.conder_subwindow = self.mdiArea.addSubWindow(self.conder)
                self.conder_subwindow.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
                self.conder.show()
                self.mdiArea.tileSubWindows()
            try:
                self.conder.open_files(con_files)
            except Exception as e:
                logging.warning(str(e))
                self.message.information(None, 'Error - Could not open selected CON files', str(e))
                pass


def main():
    # TODO Make dedicated Application class
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
