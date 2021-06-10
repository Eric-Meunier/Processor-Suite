# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'loop_planner.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from pyqtgraph import PlotWidget


class Ui_LoopPlanner(object):
    def setupUi(self, LoopPlanner):
        if not LoopPlanner.objectName():
            LoopPlanner.setObjectName(u"LoopPlanner")
        LoopPlanner.resize(1126, 783)
        self.actionSave_as_KMZ = QAction(LoopPlanner)
        self.actionSave_as_KMZ.setObjectName(u"actionSave_as_KMZ")
        icon = QIcon()
        icon.addFile(u"icons/google_earth.png", QSize(), QIcon.Normal, QIcon.Off)
        self.actionSave_as_KMZ.setIcon(icon)
        self.actionSave_as_GPX = QAction(LoopPlanner)
        self.actionSave_as_GPX.setObjectName(u"actionSave_as_GPX")
        icon1 = QIcon()
        icon1.addFile(u"icons/garmin_file.png", QSize(), QIcon.Normal, QIcon.Off)
        self.actionSave_as_GPX.setIcon(icon1)
        self.view_map_action = QAction(LoopPlanner)
        self.view_map_action.setObjectName(u"view_map_action")
        icon2 = QIcon()
        icon2.addFile(u"icons/folium.png", QSize(), QIcon.Normal, QIcon.Off)
        self.view_map_action.setIcon(icon2)
        self.actionCopy_Loop_to_Clipboard = QAction(LoopPlanner)
        self.actionCopy_Loop_to_Clipboard.setObjectName(u"actionCopy_Loop_to_Clipboard")
        self.show_grid_cbox = QAction(LoopPlanner)
        self.show_grid_cbox.setObjectName(u"show_grid_cbox")
        self.show_grid_cbox.setCheckable(True)
        self.show_grid_cbox.setChecked(True)
        self.show_annotations_cbox = QAction(LoopPlanner)
        self.show_annotations_cbox.setObjectName(u"show_annotations_cbox")
        self.show_annotations_cbox.setCheckable(True)
        self.show_annotations_cbox.setChecked(True)
        self.centralwidget = QWidget(LoopPlanner)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.centralwidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.splitter.setHandleWidth(3)
        self.splitter.setChildrenCollapsible(False)
        self.hole_frame = QFrame(self.splitter)
        self.hole_frame.setObjectName(u"hole_frame")
        sizePolicy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.hole_frame.sizePolicy().hasHeightForWidth())
        self.hole_frame.setSizePolicy(sizePolicy)
        self.hole_frame.setFrameShape(QFrame.Box)
        self.hole_frame.setFrameShadow(QFrame.Sunken)
        self.verticalLayout = QVBoxLayout(self.hole_frame)
        self.verticalLayout.setSpacing(6)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(6, 6, 6, 6)
        self.hole_cbox = QComboBox(self.hole_frame)
        self.hole_cbox.setObjectName(u"hole_cbox")

        self.verticalLayout.addWidget(self.hole_cbox)

        self.hole_tab_widget = QStackedWidget(self.hole_frame)
        self.hole_tab_widget.setObjectName(u"hole_tab_widget")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.hole_tab_widget.sizePolicy().hasHeightForWidth())
        self.hole_tab_widget.setSizePolicy(sizePolicy1)
        self.hole_tab_widget.setMinimumSize(QSize(0, 100))
        self.hole_tab_widget.setFrameShape(QFrame.Box)
        self.hole_tab_widget.setFrameShadow(QFrame.Sunken)

        self.verticalLayout.addWidget(self.hole_tab_widget)

        self.groupBox_3 = QGroupBox(self.hole_frame)
        self.groupBox_3.setObjectName(u"groupBox_3")
        sizePolicy.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy)
        self.groupBox_3.setMaximumSize(QSize(16777215, 16777215))
        self.groupBox_3.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.groupBox_3.setFlat(False)
        self.groupBox_3.setCheckable(False)
        self.gridLayout_4 = QGridLayout(self.groupBox_3)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.gps_system_cbox = QComboBox(self.groupBox_3)
        self.gps_system_cbox.setObjectName(u"gps_system_cbox")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.gps_system_cbox.sizePolicy().hasHeightForWidth())
        self.gps_system_cbox.setSizePolicy(sizePolicy2)

        self.gridLayout_4.addWidget(self.gps_system_cbox, 0, 2, 1, 1)

        self.gps_zone_cbox = QComboBox(self.groupBox_3)
        self.gps_zone_cbox.setObjectName(u"gps_zone_cbox")
        self.gps_zone_cbox.setEnabled(False)

        self.gridLayout_4.addWidget(self.gps_zone_cbox, 1, 2, 1, 1)

        self.label_6 = QLabel(self.groupBox_3)
        self.label_6.setObjectName(u"label_6")
        sizePolicy.setHeightForWidth(self.label_6.sizePolicy().hasHeightForWidth())
        self.label_6.setSizePolicy(sizePolicy)

        self.gridLayout_4.addWidget(self.label_6, 0, 1, 1, 1)

        self.label_7 = QLabel(self.groupBox_3)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout_4.addWidget(self.label_7, 1, 1, 1, 1)

        self.label_8 = QLabel(self.groupBox_3)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout_4.addWidget(self.label_8, 2, 1, 1, 1)

        self.gps_datum_cbox = QComboBox(self.groupBox_3)
        self.gps_datum_cbox.setObjectName(u"gps_datum_cbox")
        self.gps_datum_cbox.setEnabled(False)

        self.gridLayout_4.addWidget(self.gps_datum_cbox, 2, 2, 1, 1)

        self.label_15 = QLabel(self.groupBox_3)
        self.label_15.setObjectName(u"label_15")

        self.gridLayout_4.addWidget(self.label_15, 4, 1, 1, 1)

        self.epsg_edit = QLineEdit(self.groupBox_3)
        self.epsg_edit.setObjectName(u"epsg_edit")
        self.epsg_edit.setEnabled(False)
        sizePolicy2.setHeightForWidth(self.epsg_edit.sizePolicy().hasHeightForWidth())
        self.epsg_edit.setSizePolicy(sizePolicy2)

        self.gridLayout_4.addWidget(self.epsg_edit, 4, 2, 1, 1)

        self.crs_rbtn = QRadioButton(self.groupBox_3)
        self.crs_rbtn.setObjectName(u"crs_rbtn")
        self.crs_rbtn.setChecked(True)

        self.gridLayout_4.addWidget(self.crs_rbtn, 1, 0, 1, 1)

        self.epsg_rbtn = QRadioButton(self.groupBox_3)
        self.epsg_rbtn.setObjectName(u"epsg_rbtn")

        self.gridLayout_4.addWidget(self.epsg_rbtn, 4, 0, 1, 1)

        self.line_3 = QFrame(self.groupBox_3)
        self.line_3.setObjectName(u"line_3")
        sizePolicy2.setHeightForWidth(self.line_3.sizePolicy().hasHeightForWidth())
        self.line_3.setSizePolicy(sizePolicy2)
        self.line_3.setFrameShape(QFrame.HLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.gridLayout_4.addWidget(self.line_3, 3, 0, 1, 3)


        self.verticalLayout.addWidget(self.groupBox_3)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.add_hole_btn = QPushButton(self.hole_frame)
        self.add_hole_btn.setObjectName(u"add_hole_btn")
        sizePolicy2.setHeightForWidth(self.add_hole_btn.sizePolicy().hasHeightForWidth())
        self.add_hole_btn.setSizePolicy(sizePolicy2)
        icon3 = QIcon()
        icon3.addFile(u"icons/add.png", QSize(), QIcon.Normal, QIcon.Off)
        self.add_hole_btn.setIcon(icon3)
        self.add_hole_btn.setFlat(False)

        self.verticalLayout.addWidget(self.add_hole_btn)

        self.splitter.addWidget(self.hole_frame)
        self.section_frame = QFrame(self.splitter)
        self.section_frame.setObjectName(u"section_frame")
        sizePolicy3 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy3.setHorizontalStretch(30)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.section_frame.sizePolicy().hasHeightForWidth())
        self.section_frame.setSizePolicy(sizePolicy3)
        self.section_frame.setMinimumSize(QSize(0, 0))
        self.section_frame.setFrameShape(QFrame.Box)
        self.section_frame.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_2 = QVBoxLayout(self.section_frame)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.section_view_layout = QVBoxLayout()
        self.section_view_layout.setObjectName(u"section_view_layout")

        self.verticalLayout_2.addLayout(self.section_view_layout)

        self.splitter.addWidget(self.section_frame)
        self.plan_view = PlotWidget(self.splitter)
        self.plan_view.setObjectName(u"plan_view")
        sizePolicy4 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy4.setHorizontalStretch(1)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.plan_view.sizePolicy().hasHeightForWidth())
        self.plan_view.setSizePolicy(sizePolicy4)
        self.plan_view.setMinimumSize(QSize(0, 0))
        self.plan_view.setFrameShape(QFrame.Box)
        self.plan_view.setFrameShadow(QFrame.Sunken)
        self.splitter.addWidget(self.plan_view)
        self.loop_frame = QFrame(self.splitter)
        self.loop_frame.setObjectName(u"loop_frame")
        sizePolicy.setHeightForWidth(self.loop_frame.sizePolicy().hasHeightForWidth())
        self.loop_frame.setSizePolicy(sizePolicy)
        self.loop_frame.setFrameShape(QFrame.Box)
        self.loop_frame.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_3 = QVBoxLayout(self.loop_frame)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(6, 6, 6, 6)
        self.loop_cbox = QComboBox(self.loop_frame)
        self.loop_cbox.setObjectName(u"loop_cbox")

        self.verticalLayout_3.addWidget(self.loop_cbox)

        self.loop_tab_widget = QStackedWidget(self.loop_frame)
        self.loop_tab_widget.setObjectName(u"loop_tab_widget")
        sizePolicy1.setHeightForWidth(self.loop_tab_widget.sizePolicy().hasHeightForWidth())
        self.loop_tab_widget.setSizePolicy(sizePolicy1)
        self.loop_tab_widget.setMinimumSize(QSize(0, 0))
        self.loop_tab_widget.setMaximumSize(QSize(16777215, 16777215))
        self.loop_tab_widget.setFrameShape(QFrame.Box)
        self.loop_tab_widget.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_3.addWidget(self.loop_tab_widget)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer_2)

        self.add_loop_btn = QPushButton(self.loop_frame)
        self.add_loop_btn.setObjectName(u"add_loop_btn")
        sizePolicy2.setHeightForWidth(self.add_loop_btn.sizePolicy().hasHeightForWidth())
        self.add_loop_btn.setSizePolicy(sizePolicy2)
        self.add_loop_btn.setIcon(icon3)
        self.add_loop_btn.setFlat(False)

        self.verticalLayout_3.addWidget(self.add_loop_btn)

        self.splitter.addWidget(self.loop_frame)

        self.horizontalLayout.addWidget(self.splitter)

        LoopPlanner.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(LoopPlanner)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1126, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")
        LoopPlanner.setMenuBar(self.menubar)
        self.status_bar = QStatusBar(LoopPlanner)
        self.status_bar.setObjectName(u"status_bar")
        LoopPlanner.setStatusBar(self.status_bar)
        QWidget.setTabOrder(self.gps_system_cbox, self.gps_zone_cbox)
        QWidget.setTabOrder(self.gps_zone_cbox, self.gps_datum_cbox)
        QWidget.setTabOrder(self.gps_datum_cbox, self.plan_view)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menuFile.addAction(self.actionSave_as_KMZ)
        self.menuFile.addAction(self.actionSave_as_GPX)
        self.menuView.addAction(self.show_annotations_cbox)
        self.menuView.addAction(self.show_grid_cbox)
        self.menuView.addSeparator()
        self.menuView.addAction(self.view_map_action)

        self.retranslateUi(LoopPlanner)

        self.gps_system_cbox.setCurrentIndex(-1)


        QMetaObject.connectSlotsByName(LoopPlanner)
    # setupUi

    def retranslateUi(self, LoopPlanner):
        LoopPlanner.setWindowTitle(QCoreApplication.translate("LoopPlanner", u"MainWindow", None))
        self.actionSave_as_KMZ.setText(QCoreApplication.translate("LoopPlanner", u"Save as KMZ...", None))
#if QT_CONFIG(tooltip)
        self.actionSave_as_KMZ.setToolTip(QCoreApplication.translate("LoopPlanner", u"Save all GPS to a Google Earth KMZ file", None))
#endif // QT_CONFIG(tooltip)
        self.actionSave_as_GPX.setText(QCoreApplication.translate("LoopPlanner", u"Save as GPX...", None))
#if QT_CONFIG(tooltip)
        self.actionSave_as_GPX.setToolTip(QCoreApplication.translate("LoopPlanner", u"Save all GPS to a Garming GPX file", None))
#endif // QT_CONFIG(tooltip)
        self.view_map_action.setText(QCoreApplication.translate("LoopPlanner", u"Map", None))
        self.actionCopy_Loop_to_Clipboard.setText(QCoreApplication.translate("LoopPlanner", u"Copy to Clipboard", None))
        self.show_grid_cbox.setText(QCoreApplication.translate("LoopPlanner", u"Plan View Grid", None))
#if QT_CONFIG(tooltip)
        self.show_grid_cbox.setToolTip(QCoreApplication.translate("LoopPlanner", u"Show the grid in the plan view", None))
#endif // QT_CONFIG(tooltip)
        self.show_annotations_cbox.setText(QCoreApplication.translate("LoopPlanner", u"Annotations", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("LoopPlanner", u"Coordinate System", None))
        self.label_6.setText(QCoreApplication.translate("LoopPlanner", u"System:", None))
        self.label_7.setText(QCoreApplication.translate("LoopPlanner", u"Zone:", None))
        self.label_8.setText(QCoreApplication.translate("LoopPlanner", u"Datum:", None))
        self.label_15.setText(QCoreApplication.translate("LoopPlanner", u"EPSG:", None))
        self.crs_rbtn.setText("")
        self.epsg_rbtn.setText("")
        self.add_hole_btn.setText(QCoreApplication.translate("LoopPlanner", u"Add Hole", None))
        self.add_loop_btn.setText(QCoreApplication.translate("LoopPlanner", u"Add Loop", None))
        self.menuFile.setTitle(QCoreApplication.translate("LoopPlanner", u"File", None))
        self.menuView.setTitle(QCoreApplication.translate("LoopPlanner", u"View", None))
    # retranslateUi

