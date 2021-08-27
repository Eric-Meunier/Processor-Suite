# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'derotator.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from pyqtgraph import GraphicsLayoutWidget


class Ui_Derotator(object):
    def setupUi(self, Derotator):
        if not Derotator.objectName():
            Derotator.setObjectName(u"Derotator")
        Derotator.resize(1080, 701)
        self.actionPEM_File = QAction(Derotator)
        self.actionPEM_File.setObjectName(u"actionPEM_File")
        self.actionStats = QAction(Derotator)
        self.actionStats.setObjectName(u"actionStats")
        self.actionRotation_Values = QAction(Derotator)
        self.actionRotation_Values.setObjectName(u"actionRotation_Values")
        self.plot_mag_cbox = QAction(Derotator)
        self.plot_mag_cbox.setObjectName(u"plot_mag_cbox")
        self.plot_mag_cbox.setCheckable(True)
        self.plot_mag_cbox.setChecked(True)
        self.actionShow_Scatter = QAction(Derotator)
        self.actionShow_Scatter.setObjectName(u"actionShow_Scatter")
        self.actionShow_Scatter.setCheckable(True)
        self.actionShow_Scatter.setChecked(True)
        self.actionReverse_XY = QAction(Derotator)
        self.actionReverse_XY.setObjectName(u"actionReverse_XY")
        self.centralwidget = QWidget(Derotator)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout_2 = QGridLayout(self.centralwidget)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.centralwidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.splitter.setHandleWidth(2)
        self.frame = QFrame(self.splitter)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setMaximumSize(QSize(16777215, 16777215))
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Plain)
        self.gridLayout_3 = QGridLayout(self.frame)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.groupBox_2 = QGroupBox(self.frame)
        self.groupBox_2.setObjectName(u"groupBox_2")
        sizePolicy.setHeightForWidth(self.groupBox_2.sizePolicy().hasHeightForWidth())
        self.groupBox_2.setSizePolicy(sizePolicy)
        self.verticalLayout_2 = QVBoxLayout(self.groupBox_2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.soa_sbox = QSpinBox(self.groupBox_2)
        self.soa_sbox.setObjectName(u"soa_sbox")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.soa_sbox.sizePolicy().hasHeightForWidth())
        self.soa_sbox.setSizePolicy(sizePolicy1)
        self.soa_sbox.setMinimum(-359)
        self.soa_sbox.setMaximum(359)

        self.verticalLayout_2.addWidget(self.soa_sbox)


        self.gridLayout_3.addWidget(self.groupBox_2, 1, 0, 1, 1)

        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy2)
        self.verticalLayout = QVBoxLayout(self.groupBox)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.acc_btn = QRadioButton(self.groupBox)
        self.acc_btn.setObjectName(u"acc_btn")
        self.acc_btn.setChecked(True)

        self.verticalLayout.addWidget(self.acc_btn)

        self.mag_btn = QRadioButton(self.groupBox)
        self.mag_btn.setObjectName(u"mag_btn")

        self.verticalLayout.addWidget(self.mag_btn)

        self.pp_btn = QRadioButton(self.groupBox)
        self.pp_btn.setObjectName(u"pp_btn")
        self.pp_btn.setEnabled(False)

        self.verticalLayout.addWidget(self.pp_btn)

        self.none_btn = QRadioButton(self.groupBox)
        self.none_btn.setObjectName(u"none_btn")

        self.verticalLayout.addWidget(self.none_btn)

        self.separator = QFrame(self.groupBox)
        self.separator.setObjectName(u"separator")
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setFrameShadow(QFrame.Sunken)

        self.verticalLayout.addWidget(self.separator)

        self.unrotate_btn = QRadioButton(self.groupBox)
        self.unrotate_btn.setObjectName(u"unrotate_btn")

        self.verticalLayout.addWidget(self.unrotate_btn)


        self.gridLayout_3.addWidget(self.groupBox, 0, 0, 1, 1)

        self.button_box = QDialogButtonBox(self.frame)
        self.button_box.setObjectName(u"button_box")
        sizePolicy1.setHeightForWidth(self.button_box.sizePolicy().hasHeightForWidth())
        self.button_box.setSizePolicy(sizePolicy1)
        self.button_box.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.button_box.setCenterButtons(True)

        self.gridLayout_3.addWidget(self.button_box, 5, 0, 1, 1, Qt.AlignHCenter)

        self.bad_stations_label = QLabel(self.frame)
        self.bad_stations_label.setObjectName(u"bad_stations_label")
        sizePolicy.setHeightForWidth(self.bad_stations_label.sizePolicy().hasHeightForWidth())
        self.bad_stations_label.setSizePolicy(sizePolicy)
        font = QFont()
        font.setBold(True)
        font.setItalic(False)
        font.setWeight(75)
        self.bad_stations_label.setFont(font)

        self.gridLayout_3.addWidget(self.bad_stations_label, 2, 0, 1, 1)

        self.verticalSpacer = QSpacerItem(10, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_3.addItem(self.verticalSpacer, 4, 0, 1, 1)

        self.list = QLabel(self.frame)
        self.list.setObjectName(u"list")

        self.gridLayout_3.addWidget(self.list, 3, 0, 1, 1)

        self.splitter.addWidget(self.frame)
        self.frame_2 = QFrame(self.splitter)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy3 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy3.setHorizontalStretch(3)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy3)
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Plain)
        self.verticalLayout_5 = QVBoxLayout(self.frame_2)
        self.verticalLayout_5.setSpacing(0)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QTabWidget(self.frame_2)
        self.tab_widget.setObjectName(u"tab_widget")
        sizePolicy4 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.tab_widget.sizePolicy().hasHeightForWidth())
        self.tab_widget.setSizePolicy(sizePolicy4)
        self.tab_widget.setMinimumSize(QSize(0, 0))
        self.lin_tab = QWidget()
        self.lin_tab.setObjectName(u"lin_tab")
        self.verticalLayout_3 = QVBoxLayout(self.lin_tab)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.x_view = GraphicsLayoutWidget(self.lin_tab)
        self.x_view.setObjectName(u"x_view")
        self.x_view.setFrameShape(QFrame.NoFrame)

        self.verticalLayout_3.addWidget(self.x_view)

        self.tab_widget.addTab(self.lin_tab, "")
        self.log_tab = QWidget()
        self.log_tab.setObjectName(u"log_tab")
        self.verticalLayout_4 = QVBoxLayout(self.log_tab)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.y_view = GraphicsLayoutWidget(self.log_tab)
        self.y_view.setObjectName(u"y_view")
        self.y_view.setFrameShape(QFrame.NoFrame)

        self.verticalLayout_4.addWidget(self.y_view)

        self.tab_widget.addTab(self.log_tab, "")

        self.verticalLayout_5.addWidget(self.tab_widget)

        self.splitter.addWidget(self.frame_2)
        self.frame_3 = QFrame(self.splitter)
        self.frame_3.setObjectName(u"frame_3")
        sizePolicy5 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy5.setHorizontalStretch(2)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.frame_3.sizePolicy().hasHeightForWidth())
        self.frame_3.setSizePolicy(sizePolicy5)
        self.frame_3.setFrameShape(QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QFrame.Plain)
        self.verticalLayout_7 = QVBoxLayout(self.frame_3)
        self.verticalLayout_7.setSpacing(0)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.tabWidget = QTabWidget(self.frame_3)
        self.tabWidget.setObjectName(u"tabWidget")
        sizePolicy4.setHeightForWidth(self.tabWidget.sizePolicy().hasHeightForWidth())
        self.tabWidget.setSizePolicy(sizePolicy4)
        self.tabWidget.setMaximumSize(QSize(16777215, 16777215))
        self.tab_3 = QWidget()
        self.tab_3.setObjectName(u"tab_3")
        self.verticalLayout_8 = QVBoxLayout(self.tab_3)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.verticalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.deviation_view = GraphicsLayoutWidget(self.tab_3)
        self.deviation_view.setObjectName(u"deviation_view")

        self.verticalLayout_8.addWidget(self.deviation_view)

        self.tabWidget.addTab(self.tab_3, "")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName(u"tab_4")
        self.verticalLayout_9 = QVBoxLayout(self.tab_4)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.verticalLayout_9.setContentsMargins(0, 0, 0, 0)
        self.tool_view = GraphicsLayoutWidget(self.tab_4)
        self.tool_view.setObjectName(u"tool_view")

        self.verticalLayout_9.addWidget(self.tool_view)

        self.tabWidget.addTab(self.tab_4, "")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.horizontalLayout = QGridLayout(self.tab)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.rotation_view = GraphicsLayoutWidget(self.tab)
        self.rotation_view.setObjectName(u"rotation_view")
        self.rotation_view.setMinimumSize(QSize(0, 0))
        self.rotation_view.setMaximumSize(QSize(16777215, 16777215))
        self.rotation_view.setFrameShape(QFrame.NoFrame)

        self.horizontalLayout.addWidget(self.rotation_view, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.verticalLayout_6 = QVBoxLayout(self.tab_2)
        self.verticalLayout_6.setSpacing(0)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.pp_view = GraphicsLayoutWidget(self.tab_2)
        self.pp_view.setObjectName(u"pp_view")
        self.pp_view.setFrameShape(QFrame.NoFrame)

        self.verticalLayout_6.addWidget(self.pp_view)

        self.tabWidget.addTab(self.tab_2, "")

        self.verticalLayout_7.addWidget(self.tabWidget)

        self.splitter.addWidget(self.frame_3)

        self.horizontalLayout_2.addWidget(self.splitter, 0, 0, 1, 1)

        Derotator.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(Derotator)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1080, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuExport = QMenu(self.menuFile)
        self.menuExport.setObjectName(u"menuExport")
        self.menuSettings = QMenu(self.menubar)
        self.menuSettings.setObjectName(u"menuSettings")
        Derotator.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(Derotator)
        self.statusbar.setObjectName(u"statusbar")
        Derotator.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuSettings.menuAction())
        self.menuFile.addAction(self.actionReverse_XY)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.menuExport.menuAction())
        self.menuExport.addAction(self.actionPEM_File)
        self.menuExport.addAction(self.actionStats)
        self.menuSettings.addAction(self.actionShow_Scatter)

        self.retranslateUi(Derotator)

        self.tab_widget.setCurrentIndex(0)
        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(Derotator)
    # setupUi

    def retranslateUi(self, Derotator):
        Derotator.setWindowTitle(QCoreApplication.translate("Derotator", u"MainWindow", None))
        self.actionPEM_File.setText(QCoreApplication.translate("Derotator", u"PEM File", None))
        self.actionStats.setText(QCoreApplication.translate("Derotator", u"Stats", None))
        self.actionRotation_Values.setText(QCoreApplication.translate("Derotator", u"Rotation Values", None))
        self.plot_mag_cbox.setText(QCoreApplication.translate("Derotator", u"Plot Mag", None))
        self.actionShow_Scatter.setText(QCoreApplication.translate("Derotator", u"Show Scatter", None))
        self.actionReverse_XY.setText(QCoreApplication.translate("Derotator", u"Reverse XY", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("Derotator", u"Sensor Offset Angle (SOA)", None))
        self.groupBox.setTitle(QCoreApplication.translate("Derotator", u"De-rotation Method", None))
        self.acc_btn.setText(QCoreApplication.translate("Derotator", u"Accelerometer", None))
        self.mag_btn.setText(QCoreApplication.translate("Derotator", u"Magnetometer", None))
        self.pp_btn.setText(QCoreApplication.translate("Derotator", u"PP", None))
        self.none_btn.setText(QCoreApplication.translate("Derotator", u"None", None))
        self.unrotate_btn.setText(QCoreApplication.translate("Derotator", u"Un-rotate", None))
        self.bad_stations_label.setText(QCoreApplication.translate("Derotator", u"Readings ineligible for de-rotation\n"
"due to missing X and/or Y pair:", None))
        self.list.setText(QCoreApplication.translate("Derotator", u"TextLabel", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.lin_tab), QCoreApplication.translate("Derotator", u"X Component", None))
        self.tab_widget.setTabText(self.tab_widget.indexOf(self.log_tab), QCoreApplication.translate("Derotator", u"Y Component", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), QCoreApplication.translate("Derotator", u"Deviation", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_4), QCoreApplication.translate("Derotator", u"Tool Values", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("Derotator", u"Rotation", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("Derotator", u"PP Values", None))
        self.menuFile.setTitle(QCoreApplication.translate("Derotator", u"File", None))
        self.menuExport.setTitle(QCoreApplication.translate("Derotator", u"Export...", None))
        self.menuSettings.setTitle(QCoreApplication.translate("Derotator", u"Settings", None))
    # retranslateUi

