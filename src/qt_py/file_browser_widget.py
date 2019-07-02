import sys
import os
import PyQt5
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pem.pem_editor import PEMFileEditor
from qt_py.pem_file_widget import PEMFileWidget
from log import Logger
from cfg import list_of_files
from operator import itemgetter
from collections import OrderedDict
from matplotlib.backends.backend_pdf import PdfPages

logger = Logger(__name__)


class FileBrowser(QTabWidget):
    def __init__(self, parent=None):
        super().__init__()
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

    def open_files(self, file_names, **kwargs):
        def get_filename(file_path, have_suffix):
            # have_suffix will determine whether or not to include filetype in the name
            if have_suffix:
                return os.path.basename(file_path)
            else:
                st = os.path.basename(file_path)
                for i in range(len(st) - 1, -1, -1):
                    if st[i] == '.':
                        return st[0:i]
                return 'Invalid File Name'

        # Creates new tabs first before beginning the process of loading in files as opposed to calling
        # open_file in a loop which will create each tab sequentially as the files are loaded
        new_editors = []
        new_file_widgets = []

        for file_name in file_names:
            if file_name[(len(file_name) - 4):len(file_name)].lower() == '.pem':
                new_editors.append(PEMFileEditor())
                new_file_widgets.append(PEMFileWidget(parent=self, editor=new_editors[-1]))

                self.editors.append(new_editors[-1])
                self.widgets.append(new_file_widgets[-1])

                self.original_indices.append(len(self.widgets))

                # Add a new file tab
                self.addTab(new_file_widgets[-1], get_filename(file_name, True))
                # tab_widget = self.widget(tab_index)
            else:
                logger.exception('Bad Filetype', TypeError)

        for file_name, new_file_widget in zip(file_names, new_file_widgets):
            # Opening the file takes the longer so this is done in this separate
            # loop after the required widgets are generated
            new_file_widget.open_file(file_name, **kwargs)

        self.setCurrentWidget(new_file_widgets[0])
        self.active_editor = new_editors[0]

    def plotting_progress(self):
        plotted = int(0)

    def print_files(self, dir_name):
        lin_figs = OrderedDict()
        log_figs = OrderedDict()

        # Order figures by line name in ascending order
        for file_widget in self.widgets:
            components = ''.join(file_widget.editor.active_file.components)
            figures = [x.figure for x in file_widget.lin_view_widget.plot_widgets()]

            if file_widget.editor.active_file.get_header()['LineHole'] in lin_figs:
                lin_figs[file_widget.editor.active_file.get_header()['LineHole']].update({components: figures})
            else:
                lin_figs[file_widget.editor.active_file.get_header()['LineHole']] = OrderedDict({components: figures})

            if file_widget.editor.active_file.get_header()['LineHole'] in log_figs:
                log_figs[file_widget.editor.active_file.get_header()['LineHole']].update({components: figures})
            else:
                log_figs[file_widget.editor.active_file.get_header()['LineHole']] = OrderedDict({components: figures})

        for line in lin_figs.values():
            sorted(line.items(), key=lambda r: r[0])
            if 'Z' in line.items():
                line.move_to_end('Z', last=False)
        ordered_lin_figs = sorted(lin_figs.items(), key=lambda s: s[0])

        for line in log_figs.values():
            sorted(line.items(), key=lambda r: r[0])
            if 'Z' in line.items():
                line.move_to_end('Z', last=False)
        ordered_log_figs = sorted(log_figs.items(), key=lambda s: s[0])

        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        with PdfPages(os.path.join(dir_name, "lin.pdf")) as pdf:
            for line, components in ordered_lin_figs:
                for figs in components.values():
                    for fig in figs:
                        fig.set_size_inches(8.5, 11)
                        pdf.savefig(fig, dpi=fig.dpi, papertype='letter')

        with PdfPages(os.path.join(dir_name, "log.pdf")) as pdf:
            for line, components in ordered_log_figs:
                for figs in components.values():
                    for fig in figs:
                        fig.set_size_inches(8.5, 11)
                        pdf.savefig(fig, dpi=fig.dpi, papertype='letter')

        logger.info('File save complete.')

    def on_tab_close(self, index):
        logger.info("Close tab ", index)
        self.removeTab(index)
        self.editors.pop(index)
        self.widgets.pop(index)
        self.original_indices.pop(index)
        list_of_files.pop(index)

    def on_tab_move(self, from_index, to_index):
        self.editors.insert(to_index, self.editors.pop(from_index))
        self.widgets.insert(to_index, self.widgets.pop(from_index))
        self.original_indices.insert(to_index, self.original_indices.pop(from_index))
        temp = list_of_files[from_index]
        list_of_files[from_index] = list_of_files[to_index]
        list_of_files[to_index] = temp
        logger.debug('moved ' + str(from_index) + ' ' + str(to_index) + ' to new order ' + str(self.original_indices))


def main():
    app = QApplication(sys.argv)
    ex = FileBrowser()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
