import sys
import os
import re
import csv
import time
from zipfile import ZipFile
from pyunpack import Archive
from shutil import copyfile, rmtree
from pathlib import Path
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QAction,
                             QFileSystemModel, QAbstractItemView, QErrorMessage, QTableWidget)

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
        self.error = QErrorMessage()
        self.model = QFileSystemModel()

        self.dir_label.setText('')
        self.path = ''
        self.model.setRootPath(QtCore.QDir.rootPath())
        self.dir_tree.setModel(self.model)
        self.move_dir_tree_to(self.model.rootPath())
        self.calendar_widget.setSelectedDate(QtCore.QDate.currentDate())

        self.setAcceptDrops(True)

        # Actions
        self.del_file = QAction("&Remove Row", self)
        self.del_file.setShortcut("Del")
        self.del_file.triggered.connect(self.remove_row)
        self.addAction(self.del_file)

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

    def reset(self, tables_only=False):
        """
        Reset everything in the window as if it were opened anew.
        :return: None
        """
        tables = [self.dump_table, self.damp_table, self.pem_table, self.gps_table, self.geometry_table,
                  self.other_table]
        for table in tables:
            self.clear_table(table)
        if tables_only is False:
            self.dir_label.setText('')
            self.dir_tree.collapseAll()
            self.move_dir_tree_to(self.model.rootPath())

    def move_dir_tree_to(self, path):
        """
        Changes the directory tree to show the given directory.
        :param path: File path of the desired directory
        :return: None
        """
        # Adds a timer or else it doesn't actually scroll to it properly.
        QtCore.QTimer.singleShot(50, lambda: self.dir_tree.scrollTo(self.model.index(path),
                                                                    QAbstractItemView.EnsureVisible))
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
                elif url.lower().endswith('zip') or url.lower().endswith('7z') or url.lower().endswith('rar'):
                    e.accept()
                    return
        e.ignore()

    def dropEvent(self, e):
        url = [url.toLocalFile() for url in e.mimeData().urls()][0]

        if os.path.isdir(url):
            self.open_folder(url)
        elif url.lower().endswith('zip') or url.lower().endswith('7z') or url.lower().endswith('rar'):
            print(f"Extracting {os.path.basename(url)}")
            extract_dir = os.path.dirname(url)
            new_folder_dir = os.path.splitext(url)[0]

            Archive(url).extractall(extract_dir)
            self.open_folder(new_folder_dir)
            # with ZipFile(url, mode='r') as zip:
            #     print(f"Extracting {os.path.basename(url)}")
            #     extract_dir = os.path.dirname(url)
            #     zip.extractall(extract_dir)
            #     new_dir = os.path.splitext(url)[0]
            #     self.open_folder(new_dir)

    def format_widgets(self):
        self.dump_table.setColumnWidth(0, 200)
        self.damp_table.setColumnWidth(0, 200)
        self.pem_table.setColumnWidth(0, 200)
        self.gps_table.setColumnWidth(0, 200)
        self.geometry_table.setColumnWidth(0, 200)
        self.other_table.setColumnWidth(0, 200)

        self.dir_tree.setColumnHidden(1, True)
        self.dir_tree.setColumnHidden(2, True)
        self.dir_tree.setColumnHidden(3, True)

    def open_folder(self, path):
        """
        Add all the files in the directory to the tables. Attempts to add the file types to the correct tables.
        :param path: directory path of the folder
        :return: None
        """

        def add_to_table(file, dir, table):
            row = table.rowCount()
            table.insertRow(row)

            file_item = QTableWidgetItem(file)
            dir_item = QTableWidgetItem(dir)
            file_item.setFlags(file_item.flags() ^ QtCore.Qt.ItemIsDropEnabled)
            dir_item.setFlags(dir_item.flags() ^ QtCore.Qt.ItemIsDropEnabled)
            table.setItem(row, 0, file_item)
            table.setItem(row, 1, dir_item)

        self.reset(tables_only=True)
        self.path = path
        self.move_dir_tree_to(str(Path(self.path).parents[0]))
        self.dir_tree.expand(self.model.index(str(Path(self.path).parents[0])))
        self.change_dir_label()
        self.statusBar().showMessage(f"Opened {path}", 2000)
        print(f"Opened {self.path}")
        pem_extensions = ['pem']
        damp_extensions = ['log', 'rtf', 'txt']
        dump_extensions = ['dmp', 'dmp2', 'tdms', 'tdms_index', 'dat', 'xyz', 'csv']
        gps_extensions = ['ssf', 'cor', 'gdb', 'gpx', 'txt', 'csv']
        geometry_extensions = ['xls', 'xlsx', 'dad', 'seg', 'csv']

        # r=root, d=directories, f = files
        for root, dir, files in os.walk(self.path):
            for file in files:
                if any([file.lower().endswith(ext) for ext in pem_extensions]):
                    print(f"{file} is a PEM file")
                    add_to_table(file, root, self.pem_table)

                elif any([file.lower().endswith(ext) for ext in damp_extensions]) and not os.path.split(root)[
                                                                                              -1].lower() == 'gps':
                    print(f"{file} is a Damp file")
                    add_to_table(file, root, self.damp_table)

                elif any([file.lower().endswith(ext) for ext in dump_extensions]) and not os.path.split(root)[
                                                                                              -1].lower() == 'gps':
                    print(f"{file} is a Dump file")
                    add_to_table(file, root, self.dump_table)

                elif any([file.lower().endswith(ext) for ext in gps_extensions]):
                    print(f"{file} is a GPS file")
                    add_to_table(file, root, self.gps_table)

                elif any([file.lower().endswith(ext) for ext in geometry_extensions]) and not os.path.split(root)[
                                                                                                  -1].lower() == 'gps':
                    print(f"{file} is a Geometry file")
                    add_to_table(file, root, self.geometry_table)

                else:
                    print(f"{file} is another file")
                    add_to_table(file, root, self.other_table)

    def accept_changes(self):
        """
        Creates a new folder based on the date selected and organizes and copies the files in the tables into the correct
        folders. Also copies the PEM and GPS files to the working folders.
        :return: None
        """

        def make_move(folder_name, table, additional_folder=None):
            """
            Copy the files in the table to the folder_name folder.
            :param folder_name: Name of the folder to add to (or create if it doesn't exist)
            :param table: The UnpackerTable object that contains the file path information.
            :param additional_folder: path: Path of any additional folders to copy the files to.
            :return: None
            """
            if table.rowCount() > 0:
                if not os.path.isdir(os.path.join(new_folder, folder_name)):
                    os.mkdir(os.path.join(new_folder, folder_name))
                for row in range(table.rowCount()):
                    try:
                        file = table.item(row, 0).text()
                        root = table.item(row, 1).text()
                    except ValueError:
                        self.error.showMessage(f'Row {row} items does not exist')
                        return
                    else:
                        old_path = os.path.join(root, file)
                        new_path = os.path.join(os.path.join(new_folder, folder_name), file)
                        if additional_folder:
                            if not os.path.isdir(additional_folder):
                                os.mkdir(additional_folder)
                            file_name = os.path.splitext(file)[0]
                            if 'pp' in file_name.lower() or 'soa' in file_name.lower():
                                print(f"Skipping {file_name}")

                            else:
                                ext = os.path.splitext(file)[-1]
                                date_str = date.toString('dd')
                                new_file_name = f"{file_name}_{date_str}{ext}"

                                additional_path = os.path.join(additional_folder, new_file_name)
                                copyfile(old_path, additional_path)
                        try:
                            print(f"Moving \"{old_path}\" to \"{new_path}\"")
                            copyfile(old_path, new_path)
                        except FileExistsError:
                            self.error.showMessage(f'\"{new_path}\" exists already')
                        except FileNotFoundError:
                            self.error.showMessage(f'Cannot find \"{old_path}\"')

        date = self.calendar_widget.selectedDate()
        new_folder = os.path.join(str(Path(self.path).parents[0]), date.toString('MMMM dd, yyyy'))
        if os.path.isdir(new_folder):
            response = self.message.question(self, '',
                                  f"Folder \"{new_folder}\" already exists. Would you like to unpack in the existing folder?",
                                  self.message.Yes | self.message.No)
            if response == self.message.No:
                return
        else:
            os.mkdir(new_folder)

        make_move('Dump', self.dump_table)
        make_move('Damp', self.damp_table)
        make_move('PEM', self.pem_table, additional_folder=os.path.join(str(Path(self.path).parents[1]), 'RAW'))
        make_move('GPS', self.gps_table, additional_folder=os.path.join(str(Path(self.path).parents[1]), 'GPS'))
        make_move('Geometry', self.geometry_table)
        make_move('Other', self.other_table)

        self.reset(tables_only=True)
        if self.path != new_folder:
            rmtree(self.path)
        self.statusBar().showMessage('Complete.', 2000)


def main():
    app = QApplication(sys.argv)

    up = Unpacker()
    up.move(app.desktop().screen().rect().center() - up.rect().center())
    up.show()
    folder = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\MRC-111\DUMP\Oct 31st 2019'
    zip_file = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\MRC-111\DUMP\Oct 31st 2019.zip'
    # up.open_folder(folder)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
