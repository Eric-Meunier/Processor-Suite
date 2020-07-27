import sys
import os
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pem.pem_editor import PEMFileEditor
from qt_py.pem_file_widget import PEMFileWidget
from log import Logger
# from cfg import list_of_files
from operator import itemgetter
from collections import OrderedDict
from matplotlib.backends.backend_pdf import PdfPages

logger = Logger(__name__)


class FileBrowser(QTabWidget):
    def __init__(self, parent=None):
        super().__init__()

        self.editor = PEMFileEditor()

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
        self.currentChanged.connect(self.on_tab_change)

        self.files = []
        self.num_files = None
        self.num_plotted = None

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_list_item_click)
        self.pbar = QProgressBar()

    def open_file(self, file_name):
        # TODO Logic for different file types

        # new_editor = PEMFileEditor()
        new_file_widget = PEMFileWidget(parent=self, editor=self.editor)

        self.editors.append(self.editor)
        self.widgets.append(new_file_widget)
        self.original_indices.append(len(self.widgets))

        tab_index = self.addTab(new_file_widget, file_name)
        # tab_widget = self.widget(tab_index)
        self.setCurrentWidget(new_file_widget)

        new_file_widget.open(file_name)
        self.active_editor = self.editor

    def open_files(self, file_names, redraw = False, **kwargs):
        if redraw:
            self.files = list(file_names)
        else:
            self.files.extend(file_names)

        self.num_files = len(file_names)
        self.num_plotted = 0
        self.pbar.setValue(0)

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

        def get_item_name(file_path):
            self.editor.open(file_path)
            components = self.editor.active_file.get_components()
            header = self.editor.active_file.get_header()
            survey_type = self.editor.active_file.get_survey_type()
            item = header['LineHole'] + ' (' + ', '.join(components) + ')' + ' - ' + survey_type
            return str(item)

        # Creates new tabs first before beginning the process of loading in files as opposed to calling
        # open_file in a loop which will create each tab sequentially as the files are loaded
        new_editors = []
        new_file_widgets = []

        for file_name in file_names:
            if file_name[(len(file_name) - 4):len(file_name)].lower() == '.pem':
                new_editors.append(PEMFileEditor())
                new_file_widgets.append(PEMFileWidget(parent=self, editor=new_editors[-1]))

                # self.files.append(file_name)
                self.editors.append(new_editors[-1])
                self.widgets.append(new_file_widgets[-1])

                self.original_indices.append(len(self.widgets))

                # Add a new file tab
                self.addTab(new_file_widgets[-1], get_filename(file_name, True))
                self.list_widget.addItem(get_item_name(file_name))
                # tab_widget = self.widget(tab_index)
            else:
                logger.exception('Bad Filetype', TypeError)

        for file_name, new_file_widget in zip(file_names, new_file_widgets):
            # Opening the file takes the longer so this is done in this separate
            # loop after the required widgets are generated
            self.num_plotted = int(file_names.index(file_name) + 1)

            new_file_widget.open(file_name, **kwargs)
            # update = self.update_pbar()
            self.pbar.setValue(float((self.num_plotted / self.num_files) * 100))

        self.setCurrentWidget(new_file_widgets[0])
        self.active_editor = new_editors[0]
        self.list_widget.setCurrentRow(0)

    # def update_pbar(self):
    #     i = (float(((self.num_plotted-1) / self.num_files) * 100))
    #     logger.info('start')
    #     while i < (float((self.num_plotted / self.num_files) * 100)):
    #         i+=.0001
    #         self.pbar.setValue(i)
    #     logger.info('end')

    def print_files(self, dir_name):
        lin_figs = []
        log_figs = []

        # Order figures by multiple orders
        for file_widget in self.widgets:
            lin_fig_dict = OrderedDict({
                'Line': file_widget.lin_view_widget.editor.active_file.get_header()['LineHole'],
                'Loop': file_widget.lin_view_widget.editor.active_file.get_header()['Loop'],
                'Components': ''.join(file_widget.lin_view_widget.editor.active_file.components),
                'SurveyType': file_widget.lin_view_widget.editor.active_file.survey_type,
                'Timebase': file_widget.lin_view_widget.editor.active_file.get_header()['Timebase'],
                'Figures': [x.figure for x in file_widget.lin_view_widget.plot_widgets()]
            })
            lin_figs.append(lin_fig_dict)

            log_fig_dict = OrderedDict({
                'Line': file_widget.log_view_widget.editor.active_file.get_header()['LineHole'],
                'Loop': file_widget.log_view_widget.editor.active_file.get_header()['Loop'],
                'Components': ''.join(file_widget.log_view_widget.editor.active_file.components),
                'SurveyType': file_widget.log_view_widget.editor.active_file.survey_type,
                'Timebase': file_widget.log_view_widget.editor.active_file.get_header()['Timebase'],
                'Figures': [x.figure for x in file_widget.log_view_widget.plot_widgets()]
            })
            log_figs.append(log_fig_dict)

            # if file_widget.editor.active_file.get_header()['LineHole'] in log_figs:
            #     log_figs[file_widget.editor.active_file.get_header()['LineHole']].update({components: figures})
            # else:
            #     log_figs[file_widget.editor.active_file.get_header()['LineHole']] = OrderedDict({components: figures})

        lin_figs.sort(key=itemgetter('Components'), reverse=True)
        lin_figs.sort(key=itemgetter('SurveyType', 'Timebase', 'Line', 'Loop'))

        log_figs.sort(key=itemgetter('Components'), reverse=True)
        log_figs.sort(key=itemgetter('SurveyType', 'Timebase', 'Line', 'Loop'))

        # ordered_log_figs = sorted(log_figs.items(), key=lambda s: s[0])

        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        with PdfPages(os.path.join(dir_name, "lin.pdf")) as pdf:
            for line in lin_figs:
                for fig in line['Figures']:
                    fig.set_size_inches(8.5, 11)
                    pdf.savefig(fig, dpi=fig.dpi, papertype='letter')

        with PdfPages(os.path.join(dir_name, "log.pdf")) as pdf:
            for line in log_figs:
                for fig in line['Figures']:
                    fig.set_size_inches(8.5, 11)
                    pdf.savefig(fig, dpi=fig.dpi, papertype='letter')

        # with PdfPages(os.path.join(dir_name, "log.pdf")) as pdf:
        #     for line, components in ordered_log_figs:
        #         for figs in components.values():
        #             for fig in figs:
        #                 fig.set_size_inches(8.5, 11)
        #                 pdf.savefig(fig, dpi=fig.dpi, papertype='letter')

        logger.info('File save complete.')

    def on_tab_close(self, index):
        logger.info("Close tab ", index)
        self.removeTab(index)
        self.editors.pop(index)
        self.widgets.pop(index)
        self.list_widget.takeItem(index)
        self.original_indices.pop(index)
        self.files.pop(index)
        # list_of_files.pop(index)

    def on_tab_move(self, from_index, to_index):
        self.editors.insert(to_index, self.editors.pop(from_index))
        self.widgets.insert(to_index, self.widgets.pop(from_index))
        self.original_indices.insert(to_index, self.original_indices.pop(from_index))
        item = self.list_widget.takeItem(from_index)
        self.list_widget.insertItem(to_index, item)
        file = self.files.pop(from_index)
        self.files.insert(to_index, file)
        logger.debug('moved ' + str(from_index) + ' ' + str(to_index) + ' to new order ' + str(self.original_indices))

    def on_list_item_click(self):
        self.setCurrentIndex(self.list_widget.currentRow())

    def on_tab_change(self):
        try:
            self.list_widget.setCurrentRow(self.currentIndex())
        except:
            pass


def main():
    app = QApplication(sys.argv)
    ex = FileBrowser()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
