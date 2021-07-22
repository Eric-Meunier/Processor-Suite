import logging
import os
import sys
from pathlib import Path
from shutil import copyfile, rmtree

import py7zr
from PySide2.QtCore import Qt, QDir, Signal, QTimer, QDate
from PySide2.QtGui import (QIcon, QDropEvent)
from PySide2.QtWidgets import (QMainWindow, QMessageBox, QMenu, QErrorMessage,
                               QFileDialog, QVBoxLayout, QLabel, QApplication, QFrame, QHBoxLayout, QLineEdit,
                               QFileSystemModel, QTableWidgetItem, QTableWidget, QPushButton, QAbstractItemView)
from pyunpack import Archive

from src.qt_py import icons_path, get_icon, clear_table
from src.qt_py.db_plot import DBPlotter
from src.ui.unpacker import Ui_Unpacker

logger = logging.getLogger(__name__)


class Unpacker(QMainWindow, Ui_Unpacker):
    open_project_folder_sig = Signal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)

        self.setWindowTitle('Unpacker')
        self.setWindowIcon(QIcon(os.path.join(icons_path, 'unpacker_1.png')))

        self.setAcceptDrops(True)

        self.dialog = QFileDialog()
        self.message = QMessageBox()
        self.error = QErrorMessage()
        self.model = QFileSystemModel()
        self.db_plot = DBPlotter(parent=self)

        # Status bar
        dir_frame = QFrame()
        dir_frame.setLayout(QHBoxLayout())
        dir_frame.layout().setContentsMargins(2, 0, 2, 0)

        label = QLabel('Dump Directory:')
        self.dir_edit = QLineEdit('')
        self.accept_btn = QPushButton('Accept')
        self.accept_btn.setEnabled(False)
        dir_frame.layout().addWidget(label)
        dir_frame.layout().addWidget(self.dir_edit)
        dir_frame.layout().addWidget(self.accept_btn)

        self.status_bar.addWidget(dir_frame)

        self.input_path = Path()
        self.output_path = Path()
        self.model.setRootPath(QDir.rootPath())
        self.dir_tree.setModel(self.model)
        self.dir_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.dir_tree.customContextMenuRequested.connect(self.open_context_menu)
        self.move_dir_tree_to(self.model.rootPath())
        self.dir_edit.setText(self.model.rootPath())
        self.set_current_date()

        # Signals

        def dir_edit_changed():
            print(f"dir_edit editing finished.")
            path = Path(self.dir_edit.text())
            if path.is_dir():
                self.move_dir_tree_to(str(path))
                self.output_path = path
            else:
                response = self.message.question(self, 'Create Folder?', f'"{str(path)}" does not exist. '
                                                 f'Would you like to create it?', self.message.Yes, self.message.No)

                if response == self.message.Yes:

                    path.mkdir(parents=True, exist_ok=True)
                    self.move_dir_tree_to(str(path))
                    self.output_path = path
                else:

                    self.change_dir_label()

        self.accept_btn.clicked.connect(self.accept)
        self.dir_tree.clicked.connect(self.change_dir_label)
        self.dir_edit.returnPressed.connect(dir_edit_changed)
        self.open_folder_action.triggered.connect(self.open_file_dialog)
        self.reset_action.triggered.connect(self.reset)

        # Format the tables
        self.dump_frame.setLayout(QVBoxLayout())
        self.damp_frame.setLayout(QVBoxLayout())
        self.dmp_frame.setLayout(QVBoxLayout())
        self.gps_frame.setLayout(QVBoxLayout())
        self.geometry_frame.setLayout(QVBoxLayout())
        self.other_frame.setLayout(QVBoxLayout())
        self.dump_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.damp_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.dmp_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.gps_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.geometry_frame.layout().setContentsMargins(0, 0, 0, 0)
        self.other_frame.layout().setContentsMargins(0, 0, 0, 0)

        self.dump_table = UnpackerTable()
        self.damp_table = UnpackerTable()
        self.dmp_table = UnpackerTable()
        self.gps_table = UnpackerTable()
        self.geometry_table = UnpackerTable()
        self.other_table = UnpackerTable()

        self.dump_frame.layout().addWidget(self.dump_table)
        self.damp_frame.layout().addWidget(self.damp_table)
        self.dmp_frame.layout().addWidget(self.dmp_table)
        self.gps_frame.layout().addWidget(self.gps_table)
        self.geometry_frame.layout().addWidget(self.geometry_table)
        self.other_frame.layout().addWidget(self.other_table)

        self.dump_table.setColumnWidth(0, 225)
        self.damp_table.setColumnWidth(0, 225)
        self.dmp_table.setColumnWidth(0, 225)
        self.gps_table.setColumnWidth(0, 225)
        self.geometry_table.setColumnWidth(0, 225)
        self.other_table.setColumnWidth(0, 225)

        # Format the directory tree
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
        self.open_folder(url)

    def set_current_date(self):
        self.calendar_widget.setSelectedDate(QDate.currentDate())

    def closeEvent(self, e):
        self.db_plot.close()
        self.deleteLater()
        e.accept()

    def reset(self, tables_only=False):
        """
        Reset everything in the window as if it were opened anew.
        :return: None
        """
        tables = [self.dump_table, self.damp_table, self.dmp_table, self.gps_table, self.geometry_table,
                  self.other_table]
        for table in tables:
            clear_table(table)
        if tables_only is False:
            self.dir_edit.setText('')
            self.dir_tree.collapseAll()
            self.move_dir_tree_to(self.model.rootPath())
            self.set_current_date()

    def move_dir_tree_to(self, path):
        """
        Changes the directory tree to show the given directory.
        :param path: str, file path of the desired directory
        :return: None
        """
        # Adds a timer or else it doesn't actually scroll to it properly.
        QTimer.singleShot(50, lambda: self.dir_tree.scrollTo(self.model.index(path),
                                                                    QAbstractItemView.EnsureVisible))
        self.dir_tree.setCurrentIndex(self.model.index(path))

    def get_current_path(self):
        """
        Return the path of the selected directory tree item.
        :return: Path object, filepath
        """
        index = self.dir_tree.currentIndex()
        index_item = self.model.index(index.row(), 0, index.parent())
        path = self.model.filePath(index_item)
        return Path(path)

    def change_dir_label(self):
        """
        Signal slot: Changes the label of the directory label to the path of the selected item in the directory tree.
        :return: None
        """
        path = self.get_current_path()
        self.dir_edit.setText(str(path))

    def open_context_menu(self, position):
        """
        Right click context menu for directory tree
        :param position: QPoint, position of mouse at time of right-click
        """

        def add_dump_folder():
            path = self.get_current_path()
            dump_path = path.joinpath('Dump')
            dump_path.mkdir(parents=True, exist_ok=True)

        menu = QMenu()
        menu.addAction('Add Dump Folder', add_dump_folder)
        menu.exec_(self.dir_tree.viewport().mapToGlobal(position))

    def open_file_dialog(self):
        """
        Open files through the file dialog
        """
        path = Path(self.dialog.getExistingDirectory(self, 'Open Folder'))
        if path:
            self.open_folder(path)
        else:
            pass

    def open_folder(self, path, project_dir=None):
        """
        Add all the files in the directory to the tables. Attempts to add the file types to the correct tables.
        :param path: str or Path object, directory path of the folder
        :param project_dir: project directory of the parent widget. Will use this as the default path if given.
        """

        def add_to_table(file, dir, table, icon):
            """
            Add the file to the table.
            :param file: str, file name with extension
            :param dir: str, directory of the file, added to the invisible second column
            :param table: QTableWidget to add it to
            :param icon: QIcon object
            """
            row = table.rowCount()
            table.insertRow(row)

            # Add the icon
            file_item = QTableWidgetItem(icon, file)
            dir_item = QTableWidgetItem(dir)

            # Set the item flag so the item can be drag-and-dropped
            file_item.setFlags(file_item.flags() ^ Qt.ItemIsDropEnabled)
            dir_item.setFlags(dir_item.flags() ^ Qt.ItemIsDropEnabled)

            table.setItem(row, 0, file_item)
            table.setItem(row, 1, dir_item)

        if not isinstance(path, Path):
            path = Path(path)

        # Extract zipped files to a folder of the same name as the zipped file
        if path.suffix.lower() in ['.zip', '.7z', '.rar']:
            logger.info(f"Extracting {path.name}.")
            new_folder_dir = path.with_suffix('')

            # Use py7zr instead of pyunpack for 7zip files since they don't seem to work with patool
            if path.suffix == '.7z':
                with py7zr.SevenZipFile(path, mode='r') as z:
                    z.extractall(new_folder_dir)
            else:
                Archive(path).extractall(new_folder_dir, auto_create_dir=True)
            path = new_folder_dir

        self.input_path = path
        self.reset(tables_only=True)
        self.accept_btn.setEnabled(True)
        self.output_path = path

        if project_dir:
            self.move_dir_tree_to(str(path.parent))
            self.dir_edit.setText(str(path.parent))
            self.dir_tree.expand(self.model.index(str(project_dir.parent)))
        else:
            self.move_dir_tree_to(str(path.parent))
            self.dir_edit.setText(str(path.parent))
            self.dir_tree.expand(self.model.index(str(path.parent)))

        self.change_dir_label()
        self.setWindowTitle(f"Unpacker - {str(path)}")
        logger.info(f"Opened {str(self.output_path)}.")
        dmp_extensions = ['.dmp', '.dmp2', '.dmp3', '.dmp4']
        damp_extensions = ['.log', '.rtf', '.txt']
        dump_extensions = ['.pem', '.tdms', '.tdms_index', '.dat', '.xyz', '.csv']
        gps_extensions = ['.ssf', '.cor', '.gdb', '.gpx', '.txt', '.csv']
        geometry_extensions = ['.xls', '.xlsx', '.dad', '.seg', '.csv']

        damp_files = []

        # r=root, d=directories, f = files
        for root, dir, files in os.walk(str(self.output_path)):
            root_as_path = Path(root)
            for file in files:
                ext = Path(file).suffix.lower()
                icon = get_icon(Path(file))

                if any([ext in dmp_extensions]):
                    # print(f"{file} is a DMP file")
                    add_to_table(file, root, self.dmp_table, icon)

                elif any([ext in damp_extensions]) \
                        and not root_as_path.name.lower() == 'gps' \
                        and "DTL" not in file:
                    add_to_table(file, root, self.damp_table, icon)
                    damp_files.append(os.path.join(root, file))

                elif any([ext in dump_extensions]) and \
                        not root_as_path.name.lower() == 'gps':
                    add_to_table(file, root, self.dump_table, icon)

                elif any([ext in gps_extensions]):
                    add_to_table(file, root, self.gps_table, icon)

                elif any([ext in geometry_extensions]) and \
                        not root_as_path.name.lower() == 'gps':
                    add_to_table(file, root, self.geometry_table, icon)

                else:
                    add_to_table(file, root, self.other_table, icon)

        self.show()  # Show here so db_plot can show on-top
        # Plot the damping box files
        if self.open_damp_files_cbox.isChecked() and damp_files:
            self.db_plot.open(damp_files)
            if self.db_plot.db_widgets:
                self.db_plot.show()
            else:
                logger.warning(f"No DB widgets were created.")

    def accept(self):
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
            # Create a folder if folder_name isn't a folder already
            folder = new_folder.joinpath(folder_name)
            if not folder.is_dir():
                logger.info(F"Creating {folder} directory.")
                folder.mkdir(parents=True)

            if not table.rowCount():
                logger.info(F"No files found for '{folder_name}'")
                return

            for row in range(table.rowCount()):
                file = Path(table.item(row, 0).text())
                root = Path(table.item(row, 1).text())

                old_path = root.joinpath(file)
                new_path = new_folder.joinpath(folder_name).joinpath(file)

                # Copy Damp, DMP, and GPS files to an additional folder, and create the folder if it doesn't exist
                if additional_folder:
                    if not additional_folder.is_dir():  # Create the folder
                        additional_folder.mkdir(parents=True)

                    file_name = file.stem

                    # Skip soa files
                    if 'soa' in file_name.lower():
                        logger.info(f"Skipping {file}.")

                    # Copy the rest of the files to their respective folders
                    else:
                        ext = file.suffix
                        date_str = date.toString('MMdd')
                        # Rename damp files to include the date
                        if folder_name.lower() == 'damp':
                            new_file_name = f"{date_str}_{file_name}{ext}"
                        # Rename PP files to include the date
                        elif 'pp' in file_name.lower():
                            new_file_name = f"_{date_str}_{file_name}{ext}"
                        else:
                            new_file_name = f"{file_name}_{date_str}{ext}"

                        # Copy the files
                        additional_path = additional_folder.joinpath(new_file_name)
                        copyfile(old_path, additional_path)

                # Move all files in the DUMP folder. Skip if the new filepath already exists.
                if old_path.resolve() == new_path.resolve():
                    continue
                else:
                    logger.info(f"Moving {old_path} to {new_path}.")
                    try:
                        if new_path.exists():
                            logger.warning(f"{new_path.name} already exists.")
                            self.message.warning(self, "File Exists", f"{new_path} already exists.")
                            continue

                        elif not old_path.is_file():
                            logger.error(f"{old_path.name} not found.")
                            self.error.showMessage(f"{old_path.name} not found.")
                            continue

                        copyfile(old_path, new_path)
                        
                    # except FileExistsError:
                    #     logger.error(f"\"{new_path}\" exists already")
                    #     self.error.showMessage(f'\"{new_path}\" exists already')
                    # except FileNotFoundError:
                    #     logger.error(f"")
                    #     self.error.setWindowTitle('Error - File Not Found')
                    #     self.error.showMessage(f'Cannot find \"{old_path}\"')
                    except Exception as e:
                        logger.error(f"{e}.")
                        self.error.showMessage(f'{e}')
                        continue

        delete_old_folder = True
        # delete_old_folder = False
        date = self.calendar_widget.selectedDate()

        # Check if the folder already exists. If so, do not delete the folder when the process is complete.
        new_folder = self.get_current_path().joinpath(date.toString('MMMM dd, yyyy'))
        if new_folder.is_dir():
            response = self.message.question(self, 'Overwrite Folder',
                                             f"Folder {new_folder} already exists. "
                                             f"Would you like to unpack in the existing folder?",
                                             self.message.Yes | self.message.No)
            if response == self.message.No:
                return
            else:
                delete_old_folder = False
        else:
            new_folder.mkdir(parents=True, exist_ok=False)

        make_move('Dump', self.dump_table)
        make_move('Damp', self.damp_table, additional_folder=self.get_current_path().parent.joinpath('DAMP'))
        make_move('DMP', self.dmp_table, additional_folder=self.get_current_path().parent.joinpath('RAW'))
        make_move('GPS', self.gps_table, additional_folder=self.get_current_path().parent.joinpath('GPS'))
        make_move('Geometry', self.geometry_table)
        make_move('Other', self.other_table)

        # Create a "Final" folder
        final_folder = self.get_current_path().parent.joinpath('Final')
        if not final_folder.is_dir():
            final_folder.mkdir(parents=True)

        # Delete the input folder
        if self.input_path.resolve() != new_folder.resolve() and delete_old_folder is True:
            if self.input_path.resolve() in new_folder.resolve().parents:
                logger.info(f"Not removing directory {self.input_path.resolve()} as it is a part of the new folder.")
            else:
                logger.warning(f"Removing directory {self.input_path.resolve()}.")
                rmtree(self.input_path)
        # self.status_bar.showMessage('Complete.', 2000)

        # Change the project directory of PEMPro
        self.open_project_folder_sig.emit(new_folder.parents[1])
        self.close()
        # self.reset(tables_only=True)


# Must be in a different file than unpacker.py since it will create circular imports
class UnpackerTable(QTableWidget):
    """
    Re-implement a QTableWidget object to customize it
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDragEnabled(True)
        self.setDragDropOverwriteMode(False)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(['File', 'Directory'])
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.setShowGrid(False)

    def dropEvent(self, event: QDropEvent):
        if not event.isAccepted() and event.source() == self:
            drop_row = self.drop_on(event)

            rows = sorted(set(item.row() for item in self.selectedItems()))
            rows_to_move = [[QTableWidgetItem(self.item(row_index, column_index)) for column_index in range(self.columnCount())]
                            for row_index in rows]
            for row_index in reversed(rows):
                self.removeRow(row_index)
                if row_index < drop_row:
                    drop_row -= 1

            for row_index, data in enumerate(rows_to_move):
                row_index += drop_row
                self.insertRow(row_index)
                for column_index, column_data in enumerate(data):
                    self.setItem(row_index, column_index, column_data)
            event.accept()
            for row_index in range(len(rows_to_move)):
                self.item(drop_row + row_index, 0).setSelected(True)
                self.item(drop_row + row_index, 1).setSelected(True)
        super().dropEvent(event)

    def drop_on(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()

        return index.row() + 1 if self.is_below(event.pos(), index) else index.row()

    def is_below(self, pos, index):
        rect = self.visualRect(index)
        margin = 2
        if pos.y() - rect.top() < margin:
            return False
        elif rect.bottom() - pos.y() < margin:
            return True
        # noinspection PyTypeChecker
        return rect.contains(pos, True) and not (int(self.model().flags(index)) & Qt.ItemIsDropEnabled) and pos.y() >= rect.center().y()


def main():
    app = QApplication(sys.argv)
    samples_folder = Path(__file__).parents[2].joinpath(r"sample_files\Unpacker files")

    up = Unpacker()
    up.move(app.desktop().screen().rect().center() - up.rect().center())
    up.open_folder(samples_folder.joinpath(r"March 06, 2021.zip"))
    # folder = r'C:\Users\Mortulo\Desktop\Aug4DataGaribaldiResourcesNickelMountainLoop1Holes2&8Complete.zip'
    # zip_file = r'C:\Users\Eric\PycharmProjects\Crone\sample_files\PEMGetter files\__SAPR-19-003\DUMP\December 19.rar'
    # up.open_folder(folder)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
