import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pem.pem_editor import PEMFileEditor
from qt_py.pem_file_widget import PEMFileWidget
from log import Logger
logger = Logger(__name__)


class FileBrowser(QTabWidget):
    def __init__(self, parent=None):
        super(FileBrowser, self).__init__(parent)
        # self.setWindowTitle("tab demo")

        # TODO Make model to deal with these together
        self.editors = []
        self.widgets = []
        self.active_editor = None
        self.original_indices = []

        # TODO Make custom TabBar Widget to make detachable
        self.setTabsClosable(True)
        self.setMovable(True)

        self.tabCloseRequested.connect(self.on_tab_close)
        self.tabBar().tabMoved.connect(self.on_tab_move)

    def open_file(self, file_name):
        # TODO Logic for different file types

        new_editor = PEMFileEditor()
        new_file_widget = PEMFileWidget(parent=self, editor=new_editor)

        self.editors.append(new_editor)
        self.widgets.append(new_file_widget)
        self.original_indices.append(len(self.widgets))

        tab_index = self.addTab(new_file_widget, file_name)
        # tab_widget = self.widget(tab_index)
        self.setCurrentWidget(new_file_widget)

        new_file_widget.open_file(file_name)
        self.active_editor = new_editor

    def open_files(self, file_names):
        # Creates new tabs first before beginning the process of loading in files as opposed to calling
        # open_file in a loop which will create each tab sequentially as the files are loaded
        new_editors = []
        new_file_widgets = []

        for file_name in file_names:
            if file_name[(len(file_name)-4):len(file_name)].lower() == '.pem':
                new_editors.append(PEMFileEditor())
                new_file_widgets.append(PEMFileWidget(parent=self, editor=new_editors[-1]))

                self.editors.append(new_editors[-1])
                self.widgets.append(new_file_widgets[-1])
                self.original_indices.append(len(self.widgets))

                tab_index = self.addTab(new_file_widgets[-1], file_name)
                # tab_widget = self.widget(tab_index)
            else:
                raise TypeError

        for file_name, new_file_widget in zip(file_names, new_file_widgets):
            # Opening the file takes the longer so this is done in this separate
            # loop after the required widgets are generated
            new_file_widget.open_file(file_name)

        self.setCurrentWidget(new_file_widgets[0])
        self.active_editor = new_editors[0]

    def on_tab_close(self, index):
        logger.info("Close tab ", index)
        self.removeTab(index)
        self.editors.pop(index)
        self.widgets.pop(index)
        self.original_indices.pop(index)

    def on_tab_move(self, from_index, to_index):
        self.editors.insert(to_index, self.editors.pop(from_index))
        self.widgets.insert(to_index, self.widgets.pop(from_index))
        self.original_indices.insert(to_index, self.original_indices.pop(from_index))

        logger.debug('moved ' + str(from_index) + ' ' + str(to_index) + ' to new order ' + str(self.original_indices))


def main():
    app = QApplication(sys.argv)
    ex = FileBrowser()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()