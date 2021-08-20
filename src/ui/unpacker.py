# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'unpacker.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_Unpacker(object):
    def setupUi(self, Unpacker):
        if not Unpacker.objectName():
            Unpacker.setObjectName(u"Unpacker")
        Unpacker.resize(810, 761)
        self.open_folder_action = QAction(Unpacker)
        self.open_folder_action.setObjectName(u"open_folder_action")
        self.reset_action = QAction(Unpacker)
        self.reset_action.setObjectName(u"reset_action")
        self.open_damp_files_cbox = QAction(Unpacker)
        self.open_damp_files_cbox.setObjectName(u"open_damp_files_cbox")
        self.open_damp_files_cbox.setCheckable(True)
        self.open_damp_files_cbox.setChecked(True)
        self.centralwidget = QWidget(Unpacker)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(6, 6, 6, 1)
        self.frame_2 = QFrame(self.centralwidget)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setMaximumSize(QSize(450, 16777215))
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.gridLayout_3 = QGridLayout(self.frame_2)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.label_4 = QLabel(self.frame_2)
        self.label_4.setObjectName(u"label_4")
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        font.setWeight(75)
        self.label_4.setFont(font)

        self.gridLayout_3.addWidget(self.label_4, 0, 1, 1, 1, Qt.AlignHCenter)

        self.label_2 = QLabel(self.frame_2)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setFont(font)

        self.gridLayout_3.addWidget(self.label_2, 3, 0, 1, 1, Qt.AlignHCenter)

        self.damp_frame = QFrame(self.frame_2)
        self.damp_frame.setObjectName(u"damp_frame")
        self.damp_frame.setFrameShape(QFrame.StyledPanel)
        self.damp_frame.setFrameShadow(QFrame.Raised)

        self.gridLayout_3.addWidget(self.damp_frame, 1, 1, 2, 1)

        self.label_7 = QLabel(self.frame_2)
        self.label_7.setObjectName(u"label_7")
        font1 = QFont()
        font1.setBold(True)
        font1.setItalic(False)
        font1.setUnderline(False)
        font1.setWeight(75)
        self.label_7.setFont(font1)

        self.gridLayout_3.addWidget(self.label_7, 5, 1, 1, 1, Qt.AlignHCenter)

        self.receiver_frame = QFrame(self.frame_2)
        self.receiver_frame.setObjectName(u"receiver_frame")
        self.receiver_frame.setMinimumSize(QSize(20, 20))
        self.receiver_frame.setFrameShape(QFrame.StyledPanel)
        self.receiver_frame.setFrameShadow(QFrame.Raised)

        self.gridLayout_3.addWidget(self.receiver_frame, 1, 0, 2, 1)

        self.label_5 = QLabel(self.frame_2)
        self.label_5.setObjectName(u"label_5")
        font2 = QFont()
        font2.setBold(True)
        font2.setWeight(75)
        self.label_5.setFont(font2)

        self.gridLayout_3.addWidget(self.label_5, 5, 0, 1, 1, Qt.AlignHCenter)

        self.label_3 = QLabel(self.frame_2)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setFont(font)

        self.gridLayout_3.addWidget(self.label_3, 3, 1, 1, 1, Qt.AlignHCenter)

        self.label = QLabel(self.frame_2)
        self.label.setObjectName(u"label")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        self.label.setFont(font)

        self.gridLayout_3.addWidget(self.label, 0, 0, 1, 1, Qt.AlignHCenter)

        self.dmp_frame = QFrame(self.frame_2)
        self.dmp_frame.setObjectName(u"dmp_frame")
        self.dmp_frame.setFrameShape(QFrame.StyledPanel)
        self.dmp_frame.setFrameShadow(QFrame.Raised)

        self.gridLayout_3.addWidget(self.dmp_frame, 4, 0, 1, 1)

        self.gps_frame = QFrame(self.frame_2)
        self.gps_frame.setObjectName(u"gps_frame")
        self.gps_frame.setFrameShape(QFrame.StyledPanel)
        self.gps_frame.setFrameShadow(QFrame.Raised)

        self.gridLayout_3.addWidget(self.gps_frame, 4, 1, 1, 1)

        self.geometry_frame = QFrame(self.frame_2)
        self.geometry_frame.setObjectName(u"geometry_frame")
        self.geometry_frame.setFrameShape(QFrame.StyledPanel)
        self.geometry_frame.setFrameShadow(QFrame.Raised)

        self.gridLayout_3.addWidget(self.geometry_frame, 6, 0, 1, 1)

        self.other_frame = QFrame(self.frame_2)
        self.other_frame.setObjectName(u"other_frame")
        self.other_frame.setFrameShape(QFrame.StyledPanel)
        self.other_frame.setFrameShadow(QFrame.Raised)

        self.gridLayout_3.addWidget(self.other_frame, 6, 1, 1, 1)


        self.gridLayout.addWidget(self.frame_2, 11, 1, 5, 2)

        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.gridLayout_2 = QGridLayout(self.frame)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setVerticalSpacing(6)
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.calendar_widget = QCalendarWidget(self.frame)
        self.calendar_widget.setObjectName(u"calendar_widget")
        self.calendar_widget.setSelectedDate(QDate(2019, 12, 12))
        self.calendar_widget.setGridVisible(True)
        self.calendar_widget.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.calendar_widget.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar_widget.setNavigationBarVisible(True)

        self.gridLayout_2.addWidget(self.calendar_widget, 0, 0, 1, 1)

        self.dir_tree = QTreeView(self.frame)
        self.dir_tree.setObjectName(u"dir_tree")
        self.dir_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.dir_tree.setAutoExpandDelay(0)
        self.dir_tree.setRootIsDecorated(True)
        self.dir_tree.setAnimated(False)
        self.dir_tree.setHeaderHidden(True)
        self.dir_tree.header().setVisible(False)

        self.gridLayout_2.addWidget(self.dir_tree, 1, 0, 1, 1)


        self.gridLayout.addWidget(self.frame, 11, 0, 5, 1)

        Unpacker.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(Unpacker)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 810, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuSettings = QMenu(self.menubar)
        self.menuSettings.setObjectName(u"menuSettings")
        Unpacker.setMenuBar(self.menubar)
        self.status_bar = QStatusBar(Unpacker)
        self.status_bar.setObjectName(u"status_bar")
        Unpacker.setStatusBar(self.status_bar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuSettings.menuAction())
        self.menuFile.addAction(self.open_folder_action)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.reset_action)
        self.menuSettings.addAction(self.open_damp_files_cbox)

        self.retranslateUi(Unpacker)

        QMetaObject.connectSlotsByName(Unpacker)
    # setupUi

    def retranslateUi(self, Unpacker):
        Unpacker.setWindowTitle(QCoreApplication.translate("Unpacker", u"MainWindow", None))
        self.open_folder_action.setText(QCoreApplication.translate("Unpacker", u"Open Folder", None))
        self.reset_action.setText(QCoreApplication.translate("Unpacker", u"Reset", None))
        self.open_damp_files_cbox.setText(QCoreApplication.translate("Unpacker", u"Plot damping box files", None))
        self.label_4.setText(QCoreApplication.translate("Unpacker", u"Damp", None))
        self.label_2.setText(QCoreApplication.translate("Unpacker", u"DMP", None))
        self.label_7.setText(QCoreApplication.translate("Unpacker", u"Other", None))
        self.label_5.setText(QCoreApplication.translate("Unpacker", u"Geometry", None))
        self.label_3.setText(QCoreApplication.translate("Unpacker", u"GPS", None))
        self.label.setText(QCoreApplication.translate("Unpacker", u"Receiver", None))
        self.menuFile.setTitle(QCoreApplication.translate("Unpacker", u"File", None))
        self.menuSettings.setTitle(QCoreApplication.translate("Unpacker", u"Settings", None))
    # retranslateUi

