import os
import sys
from pathlib import Path
from shutil import copyfile, rmtree, unpack_archive

import numpy as np
from PyQt5 import (QtCore, QtGui, uic)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, QTableWidgetItem, QLabel,
                             QFileSystemModel, QAbstractItemView, QErrorMessage, QMenu, QDialogButtonBox,  QCheckBox)
from pyunpack import Archive
import py7zr
from src.damp.db_plot import DBPlot

# This must be placed after the custom table or else there are issues with class promotion in Qt Designer.
# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
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


class Unpacker(QMainWindow, Ui_UnpackerCreator):
    open_damp_sig = QtCore.pyqtSignal(object)
    open_dmp_sig = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)

        self.setWindowTitle('Unpacker')
        self.setWindowIcon(
            QtGui.QIcon(os.path.join(icons_path, 'unpacker_1.png')))

        self.setAcceptDrops(True)

        self.db_plot = DBPlot(parent=self)
        self.dialog = QFileDialog()
        self.message = QMessageBox()
        self.error = QErrorMessage()
        self.model = QFileSystemModel()
        self.open_damp_files_cbox = QCheckBox('Plot damping box files')
        self.open_damp_files_cbox.setChecked(True)

        self.dir_label = QLabel('')
        self.spacer_label = QLabel('')
        self.status_bar.addWidget(self.dir_label)
        self.status_bar.addWidget(self.spacer_label, 1)
        self.status_bar.addPermanentWidget(self.open_damp_files_cbox)

        self.path = ''
        self.model.setRootPath(QtCore.QDir.rootPath())
        self.dir_tree.setModel(self.model)
        self.dir_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.dir_tree.customContextMenuRequested.connect(self.open_context_menu)
        self.move_dir_tree_to(self.model.rootPath())
        self.set_current_date()

        # Signals
        self.buttonBox.accepted.connect(self.accept_changes)
        self.buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.reset)
        self.dir_tree.clicked.connect(self.change_dir_label)
        self.open_folder_action.triggered.connect(self.open_file_dialog)
        self.reset_action.triggered.connect(self.reset)

        # Format the tables and directory tree
        self.dump_table.setColumnWidth(0, 225)
        self.damp_table.setColumnWidth(0, 225)
        self.dmp_table.setColumnWidth(0, 225)
        self.gps_table.setColumnWidth(0, 225)
        self.geometry_table.setColumnWidth(0, 225)
        self.other_table.setColumnWidth(0, 225)

        self.dir_tree.setColumnHidden(1, True)
        self.dir_tree.setColumnHidden(2, True)
        self.dir_tree.setColumnHidden(3, True)

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
        url = [Path(url.toLocalFile()) for url in e.mimeData().urls()][0]

        if url.is_dir():
            self.open_folder(url)

        # Extract zipped files to a folder of the same name as the zipped file
        elif url.suffix.lower() in ['.zip', '.7z', '.rar']:
            print(f"Extracting {url.name}")
            new_folder_dir = url.with_suffix('')

            # Use py7zr instead of pyunpack for 7zip files since they don't seem to work with patool
            if url.suffix == '.7z':
                with py7zr.SevenZipFile(url, mode='r') as z:
                    z.extractall(new_folder_dir)
            else:
                Archive(url).extractall(new_folder_dir, auto_create_dir=True)
            self.open_folder(new_folder_dir)

    def set_current_date(self):
        self.calendar_widget.setSelectedDate(QtCore.QDate.currentDate())

    def closeEvent(self, e):
        self.reset()
        e.accept()

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
        tables = [self.dump_table, self.damp_table, self.dmp_table, self.gps_table, self.geometry_table,
                  self.other_table]
        for table in tables:
            self.clear_table(table)
        if tables_only is False:
            self.dir_label.setText('')
            self.dir_tree.collapseAll()
            self.move_dir_tree_to(self.model.rootPath())
            self.set_current_date()

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
        self.dir_label.setText(f" Dump directory: {path} ")

    def open_context_menu(self, position):
        """
        Right click context menu for directory tree
        :param position: QPoint, position of mouse at time of right-click
        """

        def add_dump_folder():
            path = self.get_current_path()
            dump_path = os.path.join(path, 'Dump')
            if os.path.isdir(dump_path):
                self.status_bar.showMessage('Dump folder already exists')
            else:
                os.mkdir(dump_path)

        menu = QMenu()
        menu.addAction('Add Dump Folder', add_dump_folder)
        menu.exec_(self.dir_tree.viewport().mapToGlobal(position))

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        path = self.dialog.getExistingDirectory(self, 'Open Folder')
        if path != '':
            self.open_folder(path)
        else:
            pass

    def open_folder(self, path):
        """
        Add all the files in the directory to the tables. Attempts to add the file types to the correct tables.
        :param path: directory path of the folder
        :return: None
        """

        def get_icon(ext):
            ext = ext.lower()
            if ext in ['xls', 'xlsx', 'csv']:
                icon_pix = QtGui.QPixmap(os.path.join(icons_path, 'excel_file.png'))
                icon = QtGui.QIcon(icon_pix)
            elif ext in ['rtf', 'docx', 'doc']:
                icon_pix = QtGui.QPixmap(os.path.join(icons_path, 'word_file.png'))
                icon = QtGui.QIcon(icon_pix)
            elif ext in ['log', 'txt', 'xyz', 'seg', 'dad']:
                icon_pix = QtGui.QPixmap(os.path.join(icons_path, 'txt_file.png'))
                icon = QtGui.QIcon(icon_pix)
            elif ext in ['pem', 'dmp', 'dmp2', 'dmp3', 'dmp4']:
                icon_pix = QtGui.QPixmap(os.path.join(icons_path, 'crone_logo.png'))
                icon = QtGui.QIcon(icon_pix)
            elif ext in ['gpx', 'gdb']:
                icon_pix = QtGui.QPixmap(os.path.join(icons_path, 'garmin_file.png'))
                icon = QtGui.QIcon(icon_pix)
            elif ext in ['ssf']:
                icon_pix = QtGui.QPixmap(os.path.join(icons_path, 'ssf_file.png'))
                icon = QtGui.QIcon(icon_pix)
            elif ext in ['cor']:
                icon_pix = QtGui.QPixmap(os.path.join(icons_path, 'cor_file.png'))
                icon = QtGui.QIcon(icon_pix)
            else:
                icon_pix = QtGui.QPixmap(os.path.join(icons_path, 'none_file.png'))
                icon = QtGui.QIcon(icon_pix)
            return icon

        def add_to_table(file, dir, table, extension):
            """
            Add the file to the table.
            :param file: str, file name with extension
            :param dir: str, directory of the file, added to the invisible second column
            :param table: QTableWidget to add it to
            :param extension: str, extension of the file, to be given an icon.
            """
            row = table.rowCount()
            table.insertRow(row)

            # Add the icon
            icon = get_icon(extension)
            file_item = QTableWidgetItem(icon, file)
            dir_item = QTableWidgetItem(dir)

            # Set the item flag so the item can be drag-and-dropped
            file_item.setFlags(file_item.flags() ^ QtCore.Qt.ItemIsDropEnabled)
            dir_item.setFlags(dir_item.flags() ^ QtCore.Qt.ItemIsDropEnabled)

            table.setItem(row, 0, file_item)
            table.setItem(row, 1, dir_item)

        self.reset(tables_only=True)
        self.path = path
        self.move_dir_tree_to(str(Path(self.path).parent))
        self.dir_tree.expand(self.model.index(str(Path(self.path).parent)))
        self.change_dir_label()
        self.status_bar.showMessage(f"Opened {path}", 2000)
        print(f"Opened {self.path}")
        dmp_extensions = ['dmp', 'dmp2', 'dmp3', 'dmp4']
        damp_extensions = ['log', 'rtf', 'txt']
        dump_extensions = ['pem', 'tdms', 'tdms_index', 'dat', 'xyz', 'csv']
        gps_extensions = ['ssf', 'cor', 'gdb', 'gpx', 'txt', 'csv']
        geometry_extensions = ['xls', 'xlsx', 'dad', 'seg', 'csv']

        damp_files = []

        # r=root, d=directories, f = files
        for root, dir, files in os.walk(self.path):
            for file in files:
                if any([file.lower().endswith(ext) for ext in dmp_extensions]):
                    # print(f"{file} is a DMP file")
                    ext = os.path.splitext(file)[-1][1:]
                    add_to_table(file, root, self.dmp_table, ext)

                elif any([file.lower().endswith(ext) for ext in damp_extensions]) and not os.path.split(root)[
                                                                                              -1].lower() == 'gps':
                    # print(f"{file} is a Damp file")
                    ext = os.path.splitext(file)[-1][1:]
                    add_to_table(file, root, self.damp_table, ext)
                    damp_files.append(os.path.join(root, file))

                elif any([file.lower().endswith(ext) for ext in dump_extensions]) and not os.path.split(root)[
                                                                                              -1].lower() == 'gps':
                    # print(f"{file} is a Dump file")
                    ext = os.path.splitext(file)[-1][1:]
                    add_to_table(file, root, self.dump_table, ext)

                elif any([file.lower().endswith(ext) for ext in gps_extensions]):

                    # print(f"{file} is a GPS file")
                    ext = os.path.splitext(file)[-1][1:]
                    add_to_table(file, root, self.gps_table, ext)

                elif any([file.lower().endswith(ext) for ext in geometry_extensions]) and not os.path.split(root)[
                                                                                                  -1].lower() == 'gps':
                    # print(f"{file} is a Geometry file")
                    ext = os.path.splitext(file)[-1][1:]
                    add_to_table(file, root, self.geometry_table, ext)

                else:
                    # print(f"{file} is another file")
                    ext = os.path.splitext(file)[-1][1:]
                    add_to_table(file, root, self.other_table, ext)

        # Plot the damping box files
        if self.open_damp_files_cbox.isChecked():
            self.db_plot.open(damp_files)
            self.db_plot.show()

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
            :param additional_folder: path: Path of any additional folders to copy the files to. Used for GPS, Damp,
            and DMP files. Previously used for PEM files too.
            """
            if not table.rowCount():
                return

            # Create a folder if folder_name isn't a folder already
            if not os.path.isdir(os.path.join(new_folder, folder_name)):
                os.mkdir(os.path.join(new_folder, folder_name))

            for row in range(table.rowCount()):
                file = table.item(row, 0).text()
                root = table.item(row, 1).text()

                old_path = os.path.join(root, file)
                new_path = os.path.join(os.path.join(new_folder, folder_name), file)

                # Copy Damp, DMP, and GPS files to an additional folder, and create the folder if it doesn't exist
                if additional_folder:
                    if not additional_folder.is_dir():  # Create the folder
                        os.mkdir(str(additional_folder))

                    file_name = os.path.splitext(file)[0]

                    # Skip soa files
                    if 'soa' in file_name.lower():
                        print(f"Skipping {file}")
                    # # Skip all dump files that aren't .DMP
                    # elif table == self.dump_table and \
                    #         os.path.splitext(file)[1].lower() in ['.tdms', '.tdms_index', '.dat', '.xyz', '.csv']:
                    #     print(f"Skipping {file}")

                    # Copy the rest of the files to their respective folders
                    else:
                        ext = os.path.splitext(file)[-1]
                        date_str = date.toString('dd')
                        # Rename damp files to include the date
                        if folder_name.lower() == 'damp':
                            new_file_name = f"{date_str}_{file_name}{ext}"
                        # Rename PP files to include the date
                        elif 'pp' in file_name.lower():
                            new_file_name = f"_{date_str}_{file_name}{ext}"
                        else:
                            new_file_name = f"{file_name}_{date_str}{ext}"

                        # Copy the files
                        additional_path = os.path.join(str(additional_folder), new_file_name)
                        copyfile(old_path, additional_path)

                # Move all files in the DUMP folder. Skip if the new filepath already exists.
                if os.path.abspath(old_path) == os.path.abspath(new_path):
                    continue
                else:
                    try:
                        # print(f"Moving \"{old_path}\" to \"{new_path}\"")
                        copyfile(old_path, new_path)
                    except FileExistsError:
                        self.error.setWindowTitle('Error - File Exists')
                        self.error.showMessage(f'\"{new_path}\" exists already')
                    except FileNotFoundError:
                        self.error.setWindowTitle('Error - File Not Found')
                        self.error.showMessage(f'Cannot find \"{old_path}\"')
                    except Exception as e:
                        self.error.setWindowTitle('Exception')
                        self.error.showMessage(f'{e}')
                        continue

        # delete_old_folder = True
        delete_old_folder = False
        date = self.calendar_widget.selectedDate()
        new_folder = os.path.join(self.get_current_path(), date.toString('MMMM dd, yyyy'))
        if os.path.isdir(new_folder):
            response = self.message.question(self, 'Overwrite Folder',
                                             f"Folder {new_folder} already exists. Would you like to unpack in the existing folder?",
                                             self.message.Yes | self.message.No)
            if response == self.message.No:
                return
            else:
                delete_old_folder = False
        else:
            os.mkdir(new_folder)

        make_move('Dump', self.dump_table)
        make_move('Damp', self.damp_table, additional_folder=Path(self.get_current_path()).parent.joinpath('DAMP'))
        make_move('DMP', self.dmp_table, additional_folder=Path(self.get_current_path()).parent.joinpath('RAW'))
        make_move('GPS', self.gps_table, additional_folder=Path(self.get_current_path()).parent.joinpath('GPS'))
        make_move('Geometry', self.geometry_table)
        make_move('Other', self.other_table)

        if self.path != new_folder and delete_old_folder is True:
            rmtree(self.path)
        self.status_bar.showMessage('Complete.', 2000)

        # # Plot damping box files
        # if self.open_damp_files_cbox.isChecked():
        #     # db_files = []
        #     # for row in np.arange(self.damp_table.rowCount()):
        #     #     filepath = os.path.join(self.damp_table.item(row, 0).text(), self.damp_table.item(row, 1).text())
        #     #     db_files.append(filepath)
        #     damp_dir = Path(new_folder).joinpath('Damp')
        #     db_files = list(damp_dir.glob('*.*'))
        #
        #     if db_files:
        #         self.open_damp_sig.emit(db_files)

        # Change the project directory of PEMPro
        self.open_dmp_sig.emit(Path(self.path).parents[1])

        self.reset(tables_only=True)


def main():
    app = QApplication(sys.argv)

    up = Unpacker()
    up.move(app.desktop().screen().rect().center() - up.rect().center())
    up.show()
    # folder = r'C:\Users\Mortulo\Desktop\Aug4DataGaribaldiResourcesNickelMountainLoop1Holes2&8Complete.zip'
    # zip_file = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\__SAPR-19-003\DUMP\December 19.rar'
    # up.open_folder(folder)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
