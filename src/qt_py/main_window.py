import os
import sys
import logging
from src.damp.db_plot import DBPlot
from src.con_file.confile_modder import Conder
from src.pem.pem_editor import PEMEditorWindow
from PyQt5.QtWidgets import (QWidget, QMainWindow, QApplication, QGridLayout, QDesktopWidget, QMessageBox, QMdiArea,
                             QTabWidget, QMdiSubWindow, QToolButton,
                             QFileDialog, QAbstractScrollArea, QTableWidgetItem, QMenuBar, QAction, QMenu, QToolBar)
from PyQt5 import (QtCore, QtGui, uic)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

__version__ = '0.1.0'

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

Ui_MainWindow, QtBaseClass = uic.loadUiType(MW_CreatorFile)

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


class CustomMdiArea(QMdiArea):
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        # self.mdiArea.setViewMode(QMdiArea.TabbedView)
        # self.mdiArea.setTabPosition(QTabWidget.North)
        # self.mdiArea.setTabShape(QTabWidget.Rounded)
        # self.mdiArea.setTabsClosable(True)
        # self.mdiArea.setTabsMovable(True)
        # self.setStyleSheet('cde')  # Don't notice a difference
        # self.setDocumentMode(True)  # Don't notice a difference


class CustomMdiSubWindow(QMdiSubWindow):
    closeWindow = QtCore.pyqtSignal()
    # hideWindow = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

    # def hideEvent(self, e):
    #     self.hideWindow.emit()

    def closeEvent(self, e):
        e.ignore()
        self.closeWindow.emit()
        # self.parent.clear_files()
        # self.mdiArea().tileSubWindows()  # Doesn't work, don't know why


class MainWindow(QMainWindow, Ui_MainWindow):
    windowChange = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        self.initUi()
        self.initApps()
        self.initActions()

        self.open_editor()

    def initUi(self):
        def center_window(self):
            qtRectangle = self.frameGeometry()
            centerPoint = QDesktopWidget().availableGeometry().center()
            qtRectangle.moveCenter(centerPoint)
            self.move(qtRectangle.topLeft())
            self.show()

        self.setupUi(self)  # Init for the .UI file
        self.setWindowTitle("PEMPro  v" + str(__version__))
        # self.setWindowIcon(
        #     QtGui.QIcon(os.path.join(icons_path, 'crone_logo.ico')))
        self.setGeometry(500, 300, 1500, 900)

        center_window(self)
        # self.showMaximized()

    def initApps(self):
        self.message = QMessageBox()
        self.dialog = QFileDialog()
        self.statusBar().showMessage('Ready', 2000)
        self.mdiArea = CustomMdiArea(parent=self)
        self.setCentralWidget(self.mdiArea)

        self.editor = None
        self.db_plot = None
        self.conder = None

    def initActions(self):
        # self.openFile = QAction("&Open...", self)
        # self.openFile.setShortcut("F1")
        # self.openFile.setStatusTip('Open file(s)')
        # self.openFile.triggered.connect(self.open_file_dialog)

        self.openPEMEditor = QAction("&Open PEM Editor", self)
        self.openPEMEditor.triggered.connect(self.open_editor)

        self.openDBPlot = QAction("&Open DB Plot", self)
        self.openDBPlot.triggered.connect(self.open_db_plot)

        self.openConder = QAction("&Open Conder", self)
        self.openConder.triggered.connect(self.open_conder)

        self.closeAllWindows = QAction("&Close All", self)
        self.closeAllWindows.setShortcut("Ctrl+Shift+Del")
        self.closeAllWindows.setStatusTip("Close all windows")
        self.closeAllWindows.triggered.connect(self.close_all_windows)

        self.fileMenu = self.menubar.addMenu('&File')
        self.fileMenu.addAction(self.openPEMEditor)
        self.fileMenu.addAction(self.openDBPlot)
        self.fileMenu.addAction(self.openConder)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.closeAllWindows)

        self.toolbar = QToolBar()
        self.addToolBar(QtCore.Qt.LeftToolBarArea, self.toolbar)

        self.tile_view = QAction(
            QtGui.QIcon(os.path.join(icons_path, 'windows_stack.png')),
            '&Tile View', self)
        self.tile_view.setShortcut('Ctrl+ ')
        self.tile_view.triggered.connect(self.set_view)

        self.pem_editor_button = QToolButton(self)
        self.pem_editor_button.setIcon(
            QtGui.QIcon(os.path.join(icons_path, 'plots2.png')))
        self.pem_editor_button.setCheckable(True)
        self.pem_editor_button.setStatusTip('PEM Editor')
        self.pem_editor_button.clicked.connect(self.toggle_editor)

        self.db_plot_button = QToolButton(self)
        self.db_plot_button.setIcon(
            QtGui.QIcon(os.path.join(icons_path, 'db_plot 32.png')))
        self.db_plot_button.setCheckable(True)
        self.db_plot_button.setStatusTip('DB Plot')
        self.db_plot_button.clicked.connect(self.toggle_db_plot)

        self.conder_button = QToolButton(self)
        self.conder_button.setIcon(
            QtGui.QIcon(os.path.join(icons_path, 'conder 32.png')))
        self.conder_button.setCheckable(True)
        self.conder_button.setStatusTip('Conder')
        self.conder_button.clicked.connect(self.toggle_conder)

        self.toolbar.addAction(self.tile_view)
        self.toolbar.addWidget(self.pem_editor_button)
        self.toolbar.addWidget(self.db_plot_button)
        self.toolbar.addWidget(self.conder_button)

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
                self.statusBar().showMessage('All files removed', 2000)
            else:
                pass
        else:
            pass

    def set_view(self):  # Makes the subwindow fullscreen if it's the only one up
        visible_subwindows = []
        if self.mdiArea.subWindowList():
            for subwindow in self.mdiArea.subWindowList():
                if subwindow.isHidden() == False:
                    visible_subwindows.append(subwindow)

            if len(visible_subwindows) == 1:
                visible_subwindows[0].showMaximized()
            else:
                self.mdiArea.tileSubWindows()

    def open_editor(self):
        if self.editor is None:
            self.editor = PEMEditorWindow(parent=self)
            self.editor_subwindow = CustomMdiSubWindow(parent=self.editor)
            self.editor_subwindow.setWidget(self.editor)
            self.editor_subwindow.closeWindow.connect(self.editor.clear_files)
            self.editor_subwindow.closeWindow.connect(self.toggle_editor)
            self.mdiArea.addSubWindow(self.editor_subwindow)
        self.pem_editor_button.setChecked(True)
        self.editor.show()
        self.editor_subwindow.show()
        self.set_view()

    def open_db_plot(self):
        if self.db_plot is None:
            self.db_plot = DBPlot(parent=self)
            self.db_plot_subwindow = CustomMdiSubWindow(parent=self.db_plot)
            self.db_plot_subwindow.setWidget(self.db_plot)
            self.db_plot_subwindow.closeWindow.connect(self.db_plot.clear_files)
            self.db_plot_subwindow.closeWindow.connect(self.toggle_db_plot)
            self.mdiArea.addSubWindow(self.db_plot_subwindow)
        self.db_plot_button.setChecked(True)
        self.db_plot.show()
        self.db_plot_subwindow.show()
        self.set_view()

    def open_conder(self):
        if self.conder is None:
            self.conder = Conder(parent=self)
            self.conder_subwindow = CustomMdiSubWindow(parent=self.conder)
            self.conder_subwindow.setWidget(self.conder)
            self.conder_subwindow.closeWindow.connect(self.conder.clear_files)
            self.conder_subwindow.closeWindow.connect(self.toggle_conder)
            self.mdiArea.addSubWindow(self.conder_subwindow)
        self.conder_button.setChecked(True)
        self.conder.show()
        self.conder_subwindow.show()
        self.set_view()

    def toggle_editor(self):
        if self.editor is None:
            self.open_editor()
        else:
            if self.editor_subwindow.isHidden():
                self.editor.show()
                self.editor_subwindow.show()
                self.pem_editor_button.setChecked(True)
                self.set_view()
            else:
                self.editor_subwindow.hide()
                self.pem_editor_button.setChecked(False)
                self.set_view()

    def toggle_db_plot(self):
        if self.db_plot is None:
            self.open_db_plot()
            self.set_view()
        else:
            if self.db_plot_subwindow.isHidden():
                self.db_plot.show()
                self.db_plot_subwindow.show()
                self.db_plot_button.setChecked(True)
                self.set_view()
            else:
                self.db_plot_subwindow.hide()
                self.set_view()
                self.db_plot_button.setChecked(False)

    def toggle_conder(self):
        if self.conder is None:
            self.open_conder()
        else:
            if self.conder_subwindow.isHidden():
                self.conder.show()
                self.conder_subwindow.show()
                self.conder_button.setChecked(True)
                self.set_view()
            else:
                self.conder_subwindow.hide()
                self.set_view()
                self.conder_button.setChecked(False)

    # def dragEnterEvent(self, e):
    #     urls = [url.toLocalFile().lower() for url in e.mimeData().urls()]
    #     accepted_extensions = ['pem', 'con', 'txt', 'log', 'rtf']
    #
    #     def check_extension(urls):
    #         for url in urls:
    #             url_ext = url.split('.')[-1].lower()
    #             if url_ext in accepted_extensions:
    #                 continue
    #             else:
    #                 return False
    #         return True
    #
    #     if check_extension(urls):
    #         e.accept()
    #     else:
    #         self.statusBar().showMessage('Invalid file type', 1000)
    #         e.ignore()
    #
    # def dropEvent(self, e):
    #     urls = [url.toLocalFile() for url in e.mimeData().urls()]
    #     self.open_files(urls)

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
                # if len(self.mdiArea.subWindowList()) == 1:
                #     self.editor_subwindow.showMaximized()
                # else:
                #     self.mdiArea.tileSubWindows()

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
