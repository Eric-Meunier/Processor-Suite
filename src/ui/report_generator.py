# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'report_generator.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_ReportGenerator(object):
    def setupUi(self, ReportGenerator):
        if not ReportGenerator.objectName():
            ReportGenerator.setObjectName(u"ReportGenerator")
        ReportGenerator.resize(1024, 816)
        self.centralwidget = QWidget(ReportGenerator)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.Box)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.frame)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")

        self.verticalLayout.addWidget(self.groupBox)


        self.horizontalLayout.addWidget(self.frame)

        self.group_table = QTableWidget(self.centralwidget)
        self.group_table.setObjectName(u"group_table")

        self.horizontalLayout.addWidget(self.group_table)

        self.file_table = QTableWidget(self.centralwidget)
        self.file_table.setObjectName(u"file_table")

        self.horizontalLayout.addWidget(self.file_table)

        ReportGenerator.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(ReportGenerator)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1024, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        ReportGenerator.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(ReportGenerator)
        self.statusbar.setObjectName(u"statusbar")
        ReportGenerator.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())

        self.retranslateUi(ReportGenerator)

        QMetaObject.connectSlotsByName(ReportGenerator)
    # setupUi

    def retranslateUi(self, ReportGenerator):
        ReportGenerator.setWindowTitle(QCoreApplication.translate("ReportGenerator", u"MainWindow", None))
        self.groupBox.setTitle(QCoreApplication.translate("ReportGenerator", u"GroupBox", None))
        self.menuFile.setTitle(QCoreApplication.translate("ReportGenerator", u"File", None))
    # retranslateUi

