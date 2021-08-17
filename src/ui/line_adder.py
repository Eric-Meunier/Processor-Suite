# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'line_adder.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from pyqtgraph import PlotWidget


class Ui_LineAdder(object):
    def setupUi(self, LineAdder):
        if not LineAdder.objectName():
            LineAdder.setObjectName(u"LineAdder")
        LineAdder.resize(956, 718)
        self.actionOpen = QAction(LineAdder)
        self.actionOpen.setObjectName(u"actionOpen")
        self.auto_sort_cbox = QAction(LineAdder)
        self.auto_sort_cbox.setObjectName(u"auto_sort_cbox")
        self.auto_sort_cbox.setCheckable(True)
        self.auto_sort_cbox.setChecked(True)
        self.actionEdit_Station_Names = QAction(LineAdder)
        self.actionEdit_Station_Names.setObjectName(u"actionEdit_Station_Names")
        self.actionEdit_Names = QAction(LineAdder)
        self.actionEdit_Names.setObjectName(u"actionEdit_Names")
        self.layout = QWidget(LineAdder)
        self.layout.setObjectName(u"layout")
        self.gridLayout = QGridLayout(self.layout)
        self.gridLayout.setSpacing(3)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(3, 3, 3, 3)
        self.splitter_2 = QSplitter(self.layout)
        self.splitter_2.setObjectName(u"splitter_2")
        self.splitter_2.setOrientation(Qt.Horizontal)
        self.splitter_2.setHandleWidth(2)
        self.table = QTableWidget(self.splitter_2)
        self.table.setObjectName(u"table")
        sizePolicy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.table.sizePolicy().hasHeightForWidth())
        self.table.setSizePolicy(sizePolicy)
        self.table.setMinimumSize(QSize(400, 0))
        self.table.setMaximumSize(QSize(16777215, 16777215))
        self.table.setFrameShape(QFrame.StyledPanel)
        self.table.setFrameShadow(QFrame.Plain)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.splitter_2.addWidget(self.table)
        self.frame_2 = QFrame(self.splitter_2)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Plain)
        self.verticalLayout = QVBoxLayout(self.frame_2)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.frame_2)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Vertical)
        self.splitter.setHandleWidth(2)
        self.plan_view = PlotWidget(self.splitter)
        self.plan_view.setObjectName(u"plan_view")
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(2)
        sizePolicy1.setHeightForWidth(self.plan_view.sizePolicy().hasHeightForWidth())
        self.plan_view.setSizePolicy(sizePolicy1)
        self.plan_view.setFrameShape(QFrame.NoFrame)
        self.plan_view.setFrameShadow(QFrame.Plain)
        self.splitter.addWidget(self.plan_view)
        self.section_view = PlotWidget(self.splitter)
        self.section_view.setObjectName(u"section_view")
        sizePolicy2 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(1)
        sizePolicy2.setHeightForWidth(self.section_view.sizePolicy().hasHeightForWidth())
        self.section_view.setSizePolicy(sizePolicy2)
        self.section_view.setFrameShape(QFrame.NoFrame)
        self.section_view.setFrameShadow(QFrame.Plain)
        self.splitter.addWidget(self.section_view)

        self.verticalLayout.addWidget(self.splitter)

        self.splitter_2.addWidget(self.frame_2)

        self.gridLayout.addWidget(self.splitter_2, 0, 0, 1, 1)

        self.frame = QFrame(self.layout)
        self.frame.setObjectName(u"frame")
        sizePolicy3 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy3)
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Plain)
        self.horizontalLayout = QGridLayout(self.frame)
        self.horizontalLayout.setSpacing(3)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(3, 3, 3, 3)
        self.button_box = QDialogButtonBox(self.frame)
        self.button_box.setObjectName(u"button_box")
        self.button_box.setOrientation(Qt.Horizontal)
        self.button_box.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.button_box.setCenterButtons(True)

        self.horizontalLayout.addWidget(self.button_box, 0, 0, 1, 1)


        self.gridLayout.addWidget(self.frame, 1, 0, 1, 1)

        LineAdder.setCentralWidget(self.layout)
        self.menubar = QMenuBar(LineAdder)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 956, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuSettings = QMenu(self.menubar)
        self.menuSettings.setObjectName(u"menuSettings")
        LineAdder.setMenuBar(self.menubar)
        self.status_bar = QStatusBar(LineAdder)
        self.status_bar.setObjectName(u"status_bar")
        self.status_bar.setEnabled(True)
        self.status_bar.setSizeGripEnabled(False)
        LineAdder.setStatusBar(self.status_bar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuSettings.menuAction())
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionEdit_Names)
        self.menuSettings.addAction(self.auto_sort_cbox)

        self.retranslateUi(LineAdder)

        QMetaObject.connectSlotsByName(LineAdder)
    # setupUi

    def retranslateUi(self, LineAdder):
        LineAdder.setWindowTitle(QCoreApplication.translate("LineAdder", u"MainWindow", None))
        self.actionOpen.setText(QCoreApplication.translate("LineAdder", u"Open...", None))
        self.auto_sort_cbox.setText(QCoreApplication.translate("LineAdder", u"Auto-Sort By Position", None))
        self.actionEdit_Station_Names.setText(QCoreApplication.translate("LineAdder", u"Edit Station Names", None))
        self.actionEdit_Names.setText(QCoreApplication.translate("LineAdder", u"Edit Station Names", None))
        self.menuFile.setTitle(QCoreApplication.translate("LineAdder", u"File", None))
        self.menuSettings.setTitle(QCoreApplication.translate("LineAdder", u"Settings", None))
    # retranslateUi

