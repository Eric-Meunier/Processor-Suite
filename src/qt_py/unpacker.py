import sys
import os
import re
import csv
import time
from pathlib import Path
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QAction,
                             QFileSystemModel, QAbstractItemView)

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    unpackerCreatorFile = 'qt_ui\\unpacker.ui'
    icons_path = 'icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    unpackerCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\unpacker.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_UnpackerCreator, QtBaseClass = uic.loadUiType(unpackerCreatorFile)

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook


class Unpacker(QMainWindow, Ui_UnpackerCreator):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Unpacker')
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'unpacker_1.svg')))

        self.dialog = QFileDialog()
        self.message = QMessageBox()
        self.model = QFileSystemModel()

        self.dir_label.setText('')
        self.path = ''
        self.model.setRootPath(QtCore.QDir.rootPath())
        self.dir_tree.setModel(self.model)
        self.move_to(self.model.rootPath())

        self.setAcceptDrops(True)

        # Actions
        self.del_file = QAction("&Remove Row", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_row)
        self.addAction(self.del_file)

        self.calendar_widget.showToday()
        # Signals
        self.buttonBox.accepted.connect(self.accept_changes)
        self.buttonBox.rejected.connect(self.close)
        self.dir_tree.clicked.connect(self.change_dir_label)
        self.open_folder_action.triggered.connect(self.open_file_dialog)
        self.reset_action.triggered.connect(self.reset)

        self.format_widgets()
        # self.set_date()

    def remove_row(self):
        pass

    def clear_table(self, table):
        """
        Clear a QTableWidget table.
        :param table: QTableWidget object
        :return: None
        """
        while table.rowCount() > 0:
            table.removeRow(0)

    def reset(self):
        """
        Reset everything in the window as if it were opened anew.
        :return: None
        """
        tables = [self.dump_table, self.damp_table, self.pem_table, self.gps_table, self.geometry_table, self.other_table]
        for table in tables:
            self.clear_table(table)
        self.dir_label.setText('')
        self.dir_tree.collapseAll()
        self.move_to(self.model.rootPath())

    def move_to(self, path):
        """
        Changes the directory tree to show the given directory.
        :param path: File path of the desired directory
        :return: None
        """
        # Adds a timer or else it doesn't actually scroll to it properly.
        QtCore.QTimer.singleShot(50, lambda: self.dir_tree.scrollTo(self.model.index(path),QAbstractItemView.EnsureVisible))
        self.dir_tree.setCurrentIndex(self.model.index(path))

    def get_current_path(self):
        """
        Return the path of the selected directory tree item.
        :return: str: filepath
        """
        index = self.dir_tree.currentIndex()
        index_item = self.model.index(index.row(), 0, index.parent())
        path = self.model.filePath(index_item)
        return path

    def change_dir_label(self):
        """
        Signal slot: Changes the label of the directory label to the path of the selected item in the directory tree.
        :return: None
        """
        path = self.get_current_path()
        print(f"Selected path: {path}")
        self.dir_label.setText(path)

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        path = self.dialog.getExistingDirectory(self, 'Open Folder')
        if path != '':
            self.open_folder(path)
        else:
            pass

    def dragEnterEvent(self, e):
        m = e.mimeData()
        if m.hasUrls():
            if len(m.urls()) == 1:
                url = m.urls()[0].toLocalFile()
                if os.path.isdir(url):
                    e.accept()
                    return
        e.ignore()

    def dropEvent(self, e):
        urls = [url.toLocalFile() for url in e.mimeData().urls()]
        print(f"Opening {urls[0]}")
        self.open_folder(urls[0])

    def format_widgets(self):
        self.dump_table.setColumnHidden(1, True)
        self.dump_table.setColumnHidden(2, True)
        self.damp_table.setColumnHidden(1, True)
        self.damp_table.setColumnHidden(2, True)
        self.pem_table.setColumnHidden(1, True)
        self.pem_table.setColumnHidden(2, True)
        self.gps_table.setColumnHidden(1, True)
        self.gps_table.setColumnHidden(2, True)
        self.geometry_table.setColumnHidden(1, True)
        self.geometry_table.setColumnHidden(2, True)
        self.other_table.setColumnHidden(1, True)
        self.other_table.setColumnHidden(2, True)

        self.dir_tree.setColumnHidden(1, True)
        self.dir_tree.setColumnHidden(2, True)
        self.dir_tree.setColumnHidden(3, True)

    def open_folder(self, path):

        def add_to_table(file, dir, table):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(file))
            table.setItem(row, 1, QTableWidgetItem(dir))

        self.path = path
        self.move_to(str(Path(self.path).parents[0]))
        self.dir_tree.expand(self.model.index(str(Path(self.path).parents[0])))
        self.change_dir_label()
        self.statusBar().showMessage(f"Opened {path}", 2000)
        print(f"Opened {self.path}")
        pem_extensions = ['pem']
        damp_extensions = ['log', 'rtf', 'txt']
        dump_extensions = ['dmp', 'dmp2', 'tdms', 'tdms_index', 'dat', 'xyz', 'csv']
        gps_extensions = ['ssf', 'cor', 'gdb', 'gpx', 'txt']
        geometry_extensions = ['xls', 'xlsx', 'dad', 'seg', 'csv']

        # r=root, d=directories, f = files
        for root, dir, files in os.walk(self.path):
            for file in files:
                if any([file.lower().endswith(ext) for ext in pem_extensions]):
                    print(f"{file} is a PEM file")
                    add_to_table(file, root, self.pem_table)

                elif any([file.lower().endswith(ext) for ext in damp_extensions]) and not os.path.split(root)[-1].lower() == 'gps':
                    print(f"{file} is a Damp file")
                    add_to_table(file, root, self.damp_table)

                elif any([file.lower().endswith(ext) for ext in dump_extensions]):
                    print(f"{file} is a Dump file")
                    add_to_table(file, root, self.dump_table)

                elif any([file.lower().endswith(ext) for ext in gps_extensions]):
                    print(f"{file} is a GPS file")
                    add_to_table(file, root, self.gps_table)

                elif any([file.lower().endswith(ext) for ext in geometry_extensions]):
                    print(f"{file} is a Geometry file")
                    add_to_table(file, root, self.geometry_table)

                else:
                    print(f"{file} is another file")
                    add_to_table(file, root, self.other_table)

    def accept_changes(self):

        def make_move(folder_name, table, append_date=False):
            if table.rowCount() > 0:
                if not os.path.isdir(os.path.join(new_folder, folder_name)):
                    os.mkdir(os.path.join(new_folder, folder_name))
                for row in range(table.rowCount()):
                    file = table.item(row, 0).text()
                    root = table.item(row, 1).text()
                    old_path = os.path.join(root, file)
                    new_path = os.path.join(os.path.join(new_folder, folder_name), file)
                    if append_date:
                        new_path = os.path.join(new_path, add file and date )
                    os.rename(old_path, new_path)


        date = QtCore.QDate.getDate(self.calendar_widget.selectedDate())
        new_folder = os.path.join(str(Path(self.path).parents[0]), str(date))
        if not os.path.isdir(new_folder):
            os.mkdir(new_folder)

        make_move('Dump', self.dump_table)
        make_move('Damp', self.damp_table)
        make_move('PEM', self.pem_table, append_date=True)
        make_move('GPS', self.gps_table, append_date=True)
        make_move('Geometry', self.geometry_table)
        make_move('Other', self.other_table)


def main():
    app = QApplication(sys.argv)

    up = Unpacker()
    up.move(app.desktop().screen().rect().center() - up.rect().center())
    up.show()
    folder = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\MRC-111\DUMP\Oct 31st 2019'
    up.open_folder(folder)


    sys.exit(app.exec())


if __name__ == '__main__':
    main()
