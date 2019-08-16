import os
import sys
import logging
from src.damp.db_plot import DBPlot
from src.con_file.confile_modder import Conder
from src.pem.new_pem_editor import PEMEditorWindow
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox, QMdiArea,
                             QTabWidget, QMdiSubWindow,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem, QMenuBar, QAction, QMenu, QToolBar)
from PyQt5 import (QtCore, QtGui, uic)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

__version__ = '0.0.2'

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the pyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = sys._MEIPASS
    MW_CreatorFile = 'qt_ui\\main_window.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    MW_CreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\main_window.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# MW_CreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\main_window.ui')
Ui_MainWindow, QtBaseClass = uic.loadUiType(MW_CreatorFile)


class CustomMdiArea(QMdiArea):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent


class CustomMdiSubWindow(QMdiSubWindow):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

    def closeEvent(self, e):
        self.parent.clear_files()
        self.window().mdiArea.tileSubWindows()  # Doesn't work, don't know why
        e.accept()


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
            QtGui.QIcon(os.path.join(icons_path, 'crone_logo.ico')))
        self.setGeometry(500, 300, 1400, 900)
        center_window(self)

    def initApps(self):
        self.message = QMessageBox()
        self.dialog = QFileDialog()
        self.statusbar.showMessage('Ready', 2000)
        self.mdiArea = CustomMdiArea(parent=self)
        self.setCentralWidget(self.mdiArea)
        self.mdiArea.setViewMode(QMdiArea.TabbedView)
        self.mdiArea.setTabPosition(QTabWidget.North)
        self.mdiArea.setTabShape(QTabWidget.Rounded)
        # self.mdiArea.setTabsClosable(True)
        self.mdiArea.setTabsMovable(True)
        # self.mdiArea.setStyleSheet('cde')  # Don't notice a difference
        # self.mdiArea.setDocumentMode(True)  # Don't notice a difference

        self.editor = None
        self.db_plot = None
        self.conder = None

    def initActions(self):
        self.openFile = QAction("&Open...", self)
        self.openFile.setShortcut("F1")
        self.openFile.setStatusTip('Open file(s)')
        self.openFile.triggered.connect(self.open_file_dialog)

        self.closeAllWindows = QAction("&Close All", self)
        self.closeAllWindows.setShortcut("Ctrl+Shift+Del")
        self.closeAllWindows.setStatusTip("Close all windows")
        self.closeAllWindows.triggered.connect(self.close_all_windows)

        # self.clearFiles = QAction("&Clear All Files", self)
        # self.clearFiles.setShortcut("Ctrl+Del")
        # self.clearFiles.setStatusTip("Clear all files")
        # self.clearFiles.triggered.connect(self.clear_files)

        self.fileMenu = self.menubar.addMenu('&File')
        self.fileMenu.addAction(self.openFile)
        self.fileMenu.addAction(self.closeAllWindows)
        # self.fileMenu.addAction(self.clearFiles)

        self.toolbar = QToolBar()
        self.addToolBar(QtCore.Qt.LeftToolBarArea, self.toolbar)

        self.tile_view = QAction(
            QtGui.QIcon(os.path.join(icons_path, 'windows_stack.png')),
            '&Tile View', self)
        self.tile_view.setShortcut('Ctrl+ ')
        self.tile_view.triggered.connect(self.set_tile_view)

        self.show_pem_editor = QAction(
            QtGui.QIcon(os.path.join(icons_path, 'plots2.png')), '&PEM Editor', self)
        self.show_pem_editor.triggered.connect(self.toggle_editor)

        self.show_db_plot = QAction(
            QtGui.QIcon(os.path.join(icons_path, 'db_plot 32.png')), '&DB Plot', self)
        self.show_db_plot.triggered.connect(self.toggle_db_plot)

        self.show_conder = QAction(
            QtGui.QIcon(os.path.join(icons_path, 'conder.png')), '&Conder', self)
        self.show_conder.triggered.connect(self.toggle_conder)

        self.toolbar.addAction(self.tile_view)
        self.toolbar.addAction(self.show_pem_editor)
        self.toolbar.addAction(self.show_db_plot)
        self.toolbar.addAction(self.show_conder)

    def set_tile_view(self):
        self.mdiArea.tileSubWindows()

    def close_all_windows(self):
        if self.mdiArea.subWindowList():
            response = self.message.question(self, 'PEMPro', 'Are you sure you want to close all windows?',
                                             self.message.Yes | self.message.No)
            if response == self.message.Yes:
                self.mdiArea.closeAllSubWindows()
                self.clear_files(response=self.message.Yes)
            else:
                pass
        else:
            pass

    def clear_files(self, response=None):
        if self.editor or self.db_plot or self.conder:
            if response is None:
                response = self.message.question(self, 'PEMPro', 'Are you sure you want to clear all files?',
                                                 self.message.Yes | self.message.No)

            if response == self.message.Yes:
                if self.editor:
                    self.editor.clear_files()
                if self.db_plot:
                    self.db_plot.clear_files()
                if self.conder:
                    self.conder.clear_files()
                self.statusbar.showMessage('All files removed', 2000)
            else:
                pass
        else:
            pass

    def open_editor(self):
        self.editor = PEMEditorWindow(parent=self)
        self.editor_subwindow = CustomMdiSubWindow(parent=self.editor)
        self.editor_subwindow.setWidget(self.editor)
        self.mdiArea.addSubWindow(self.editor_subwindow)

    def open_db_plot(self):
        self.db_plot = DBPlot(parent=self)
        self.db_plot_subwindow = CustomMdiSubWindow(parent=self.db_plot)
        self.db_plot_subwindow.setWidget(self.db_plot)
        self.mdiArea.addSubWindow(self.db_plot_subwindow)

    def open_conder(self):
        self.conder = Conder(parent=self)
        self.conder_subwindow = CustomMdiSubWindow(parent=self.conder)
        self.conder_subwindow.setWidget(self.conder)
        self.mdiArea.addSubWindow(self.conder_subwindow)

    def toggle_editor(self):
        if self.editor is None:
            self.open_editor()
            if len(self.mdiArea.subWindowList()) == 1:
                self.editor_subwindow.showMaximized()
            else:
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
            self.open_db_plot()
            if len(self.mdiArea.subWindowList()) == 1:
                self.db_plot_subwindow.showMaximized()
            else:
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
            self.open_conder()
            if len(self.mdiArea.subWindowList()) == 1:
                self.conder_subwindow.showMaximized()
            else:
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
            self.statusbar.showMessage('Invalid file type', 1000)
            e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        self.open_files(urls)

    def open_file_dialog(self):
        accepted_extensions = ['pem', 'con', 'txt', 'log', 'rtf']
        try:
            files = self.dialog.getOpenFileNames(self, 'Open Files',
                                                 filter='All Files (*.*);; PEM files (*.pem);; '
                                                        'Damp files (*.txt *.log *.rtf);; CON files (*.con)')
            if files[0] != '':
                for file in files[0]:
                    if file.split('.')[-1].lower() in accepted_extensions:
                        self.open_files(file)
                    else:
                        pass
            else:
                pass
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
                self.open_editor()
            try:
                self.editor.open_files(pem_files)
            except Exception as e:
                logging.warning(str(e))
                self.message.information(None, 'Error - Could not open selected PEM files', str(e))
                pass
            else:
                self.editor.show()
                self.editor_subwindow.show()
                if len(self.mdiArea.subWindowList()) == 1:
                    self.editor_subwindow.showMaximized()
                else:
                    self.mdiArea.tileSubWindows()

        if len(damp_files) > 0:
            if self.db_plot is None:
                self.open_db_plot()
            try:
                self.db_plot.open_files(damp_files)
            except Exception as e:
                logging.warning(str(e))
                self.message.information(None, 'Error - Could not open selected damping box files', str(e))
                pass
            else:
                self.db_plot.show()
                self.db_plot_subwindow.show()
                if len(self.mdiArea.subWindowList()) == 1:
                    self.db_plot_subwindow.showMaximized()
                else:
                    self.mdiArea.tileSubWindows()

        if len(con_files) > 0:
            if self.conder is None:
                self.open_conder()
            try:
                self.conder.open_files(con_files)
            except Exception as e:
                logging.warning(str(e))
                self.message.information(None, 'Error - Could not open selected CON files', str(e))
                pass
            else:
                self.conder.show()
                self.conder_subwindow.show()
                if len(self.mdiArea.subWindowList()) == 1:
                    self.conder_subwindow.showMaximized()
                else:
                    self.mdiArea.tileSubWindows()


# class

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
