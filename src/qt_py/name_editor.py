import logging
import os
import sys

from PyQt5 import (QtCore, uic)
from PyQt5.QtWidgets import (QWidget, QAbstractScrollArea, QTableWidgetItem, QHeaderView)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)

# Modify the paths for when the script is being run in a frozen state (i.e. as an EXE)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    lineNameEditorCreatorFile = 'qt_ui\\line_name_editor.ui'
    icons_path = 'qt_ui\\icons'
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    lineNameEditorCreatorFile = os.path.join(os.path.dirname(application_path), 'qt_ui\\line_name_editor.ui')
    icons_path = os.path.join(os.path.dirname(application_path), "qt_ui\\icons")

# Load Qt ui file into a class
Ui_LineNameEditorWidget, QtBaseClass = uic.loadUiType(lineNameEditorCreatorFile)


class BatchNameEditor(QWidget, Ui_LineNameEditorWidget):
    """
    Class to bulk rename PEM File line/hole names or file names.
    """
    acceptChangesSignal = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.setupUi(self)
        self.pem_files = []
        self.kind = None

        self.table_columns = ['Old Name', 'New Name']
        self.table.setColumnCount(len(self.table_columns))
        self.table.setHorizontalHeaderLabels(self.table_columns)
        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.addEdit.textEdited.connect(self.update_table)
        self.removeEdit.textEdited.connect(self.update_table)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.accepted.connect(self.accept_changes)

    def open(self, pem_files, kind=None):
        """
        Open the pem_files
        :param pem_files: list, PEMFile objects
        :param kind: str, either 'Line' to change the line names or 'File' to change file names
        :return: None
        """
        # Reset
        self.addEdit.setText('[n]')
        self.removeEdit.setText('')
        while self.table.rowCount() > 0:
            self.table.removeRow(0)

        self.pem_files = pem_files
        self.kind = kind

        if self.kind == 'Line':
            self.setWindowTitle('Rename lines/holes names')
        else:
            self.setWindowTitle('Rename files names')

        for pem_file in self.pem_files:
            self.add_to_table(pem_file)

        self.show()

    def add_to_table(self, pem_file):
        """
        Add the PEM files to the table.
        :param pem_file: PEMFile object
        """
        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        if self.kind == 'Line':
            item = QTableWidgetItem(pem_file.line_name)
            item2 = QTableWidgetItem(pem_file.line_name)
        elif self.kind == 'File':
            item = QTableWidgetItem(pem_file.filepath.name)
            item2 = QTableWidgetItem(pem_file.filepath.name)
        else:
            raise ValueError(f'{self.kind} is not a valid option.')

        item.setTextAlignment(QtCore.Qt.AlignCenter)
        item2.setTextAlignment(QtCore.Qt.AlignCenter)

        self.table.setItem(row_pos, 0, item)
        self.table.setItem(row_pos, 1, item2)

        self.table.resizeColumnsToContents()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif e.key() == QtCore.Qt.Key_Return:
            self.accept_changes()

    def update_table(self):
        """
        Every time a change is made in the line edits, this function is called and updates the entries in the table
        """
        for row in range(self.table.rowCount()):
            # Split the text based on '[n]'. Anything before it becomes the prefix,
            # and everything after is added as a suffix
            if self.kind == 'Line':
                # Immediately replace what's in the removeEdit object with nothing
                input = self.table.item(row, 0).text().replace(self.removeEdit.text(), '')
                suffix = self.addEdit.text().rsplit('[n]')[-1]
                prefix = self.addEdit.text().rsplit('[n]')[0]
                output = prefix + input + suffix
            else:
                input = self.table.item(row, 0).text().split('.')[0].replace(self.removeEdit.text(), '')
                ext = '.' + self.table.item(row, 0).text().split('.')[-1]
                suffix = self.addEdit.text().rsplit('[n]')[-1]
                prefix = self.addEdit.text().rsplit('[n]')[0]
                output = prefix + input + suffix + ext

            item = QTableWidgetItem(output)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 1, item)

    def accept_changes(self):
        """
        Create a list of the new names and emit them as a signal
        """

        new_names = []
        for i, pem_file in enumerate(self.pem_files):
            new_name = self.table.item(i, 1).text()
            new_names.append(new_name)

        self.acceptChangesSignal.emit(new_names)

