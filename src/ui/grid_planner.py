# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'grid_planner.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from pyqtgraph import PlotWidget


class Ui_GridPlanner(object):
    def setupUi(self, GridPlanner):
        if not GridPlanner.objectName():
            GridPlanner.setObjectName(u"GridPlanner")
        GridPlanner.resize(1126, 867)
        self.actionSave_as_KMZ = QAction(GridPlanner)
        self.actionSave_as_KMZ.setObjectName(u"actionSave_as_KMZ")
        self.actionSave_as_GPX = QAction(GridPlanner)
        self.actionSave_as_GPX.setObjectName(u"actionSave_as_GPX")
        self.view_map_action = QAction(GridPlanner)
        self.view_map_action.setObjectName(u"view_map_action")
        self.actionCopy_Grid_to_Clipboard = QAction(GridPlanner)
        self.actionCopy_Grid_to_Clipboard.setObjectName(u"actionCopy_Grid_to_Clipboard")
        self.actionCopy_Loop_to_Clipboard = QAction(GridPlanner)
        self.actionCopy_Loop_to_Clipboard.setObjectName(u"actionCopy_Loop_to_Clipboard")
        self.centralwidget = QWidget(GridPlanner)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.centralwidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.splitter.setHandleWidth(2)
        self.frame_2 = QFrame(self.splitter)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy)
        self.frame_2.setMaximumSize(QSize(16777215, 16777215))
        self.frame_2.setFrameShape(QFrame.Box)
        self.frame_2.setFrameShadow(QFrame.Sunken)
        self.verticalLayout = QVBoxLayout(self.frame_2)
        self.verticalLayout.setSpacing(6)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(6, 6, 6, 6)
        self.tx_loop_gbox = QGroupBox(self.frame_2)
        self.tx_loop_gbox.setObjectName(u"tx_loop_gbox")
        sizePolicy.setHeightForWidth(self.tx_loop_gbox.sizePolicy().hasHeightForWidth())
        self.tx_loop_gbox.setSizePolicy(sizePolicy)
        self.tx_loop_gbox.setMaximumSize(QSize(16777215, 16777215))
        self.tx_loop_gbox.setCheckable(False)
        self.gridLayout_2 = QGridLayout(self.tx_loop_gbox)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.label_4 = QLabel(self.tx_loop_gbox)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_2.addWidget(self.label_4, 3, 0, 1, 1)

        self.label_3 = QLabel(self.tx_loop_gbox)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_2.addWidget(self.label_3, 1, 0, 1, 1)

        self.label_2 = QLabel(self.tx_loop_gbox)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_2.addWidget(self.label_2, 2, 0, 1, 1)

        self.label_12 = QLabel(self.tx_loop_gbox)
        self.label_12.setObjectName(u"label_12")

        self.gridLayout_2.addWidget(self.label_12, 5, 0, 1, 1)

        self.line = QFrame(self.tx_loop_gbox)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.gridLayout_2.addWidget(self.line, 4, 0, 1, 2)

        self.loop_name_edit = QLineEdit(self.tx_loop_gbox)
        self.loop_name_edit.setObjectName(u"loop_name_edit")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.loop_name_edit.sizePolicy().hasHeightForWidth())
        self.loop_name_edit.setSizePolicy(sizePolicy1)

        self.gridLayout_2.addWidget(self.loop_name_edit, 5, 1, 1, 1)

        self.include_loop_cbox = QCheckBox(self.tx_loop_gbox)
        self.include_loop_cbox.setObjectName(u"include_loop_cbox")
        sizePolicy1.setHeightForWidth(self.include_loop_cbox.sizePolicy().hasHeightForWidth())
        self.include_loop_cbox.setSizePolicy(sizePolicy1)

        self.gridLayout_2.addWidget(self.include_loop_cbox, 6, 0, 1, 2)

        self.loop_height_sbox = QSpinBox(self.tx_loop_gbox)
        self.loop_height_sbox.setObjectName(u"loop_height_sbox")
        self.loop_height_sbox.setMinimum(1)
        self.loop_height_sbox.setMaximum(10000)
        self.loop_height_sbox.setSingleStep(10)
        self.loop_height_sbox.setValue(1000)

        self.gridLayout_2.addWidget(self.loop_height_sbox, 1, 1, 1, 1)

        self.loop_width_sbox = QSpinBox(self.tx_loop_gbox)
        self.loop_width_sbox.setObjectName(u"loop_width_sbox")
        self.loop_width_sbox.setMinimum(1)
        self.loop_width_sbox.setMaximum(10000)
        self.loop_width_sbox.setSingleStep(10)
        self.loop_width_sbox.setValue(1000)

        self.gridLayout_2.addWidget(self.loop_width_sbox, 2, 1, 1, 1)

        self.loop_angle_sbox = QSpinBox(self.tx_loop_gbox)
        self.loop_angle_sbox.setObjectName(u"loop_angle_sbox")
        self.loop_angle_sbox.setMaximum(360)
        self.loop_angle_sbox.setSingleStep(5)

        self.gridLayout_2.addWidget(self.loop_angle_sbox, 3, 1, 1, 1)


        self.verticalLayout.addWidget(self.tx_loop_gbox)

        self.groupBox = QGroupBox(self.frame_2)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setMaximumSize(QSize(16777215, 16777215))
        self.gridLayout_3 = QGridLayout(self.groupBox)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.line_2 = QFrame(self.groupBox)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.HLine)
        self.line_2.setFrameShadow(QFrame.Sunken)

        self.gridLayout_3.addWidget(self.line_2, 7, 1, 1, 2)

        self.label_13 = QLabel(self.groupBox)
        self.label_13.setObjectName(u"label_13")

        self.gridLayout_3.addWidget(self.label_13, 8, 1, 1, 1)

        self.grid_name_edit = QLineEdit(self.groupBox)
        self.grid_name_edit.setObjectName(u"grid_name_edit")
        sizePolicy1.setHeightForWidth(self.grid_name_edit.sizePolicy().hasHeightForWidth())
        self.grid_name_edit.setSizePolicy(sizePolicy1)

        self.gridLayout_3.addWidget(self.grid_name_edit, 8, 2, 1, 1)

        self.label_14 = QLabel(self.groupBox)
        self.label_14.setObjectName(u"label_14")

        self.gridLayout_3.addWidget(self.label_14, 4, 1, 1, 1)

        self.label_10 = QLabel(self.groupBox)
        self.label_10.setObjectName(u"label_10")

        self.gridLayout_3.addWidget(self.label_10, 6, 1, 1, 1)

        self.label_9 = QLabel(self.groupBox)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_3.addWidget(self.label_9, 2, 1, 1, 1)

        self.label = QLabel(self.groupBox)
        self.label.setObjectName(u"label")
        sizePolicy2 = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy2)

        self.gridLayout_3.addWidget(self.label, 0, 1, 1, 1)

        self.label_5 = QLabel(self.groupBox)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_3.addWidget(self.label_5, 1, 1, 1, 1)

        self.label_11 = QLabel(self.groupBox)
        self.label_11.setObjectName(u"label_11")

        self.gridLayout_3.addWidget(self.label_11, 5, 1, 1, 1)

        self.label_15 = QLabel(self.groupBox)
        self.label_15.setObjectName(u"label_15")

        self.gridLayout_3.addWidget(self.label_15, 3, 1, 1, 1)

        self.grid_easting_sbox = QSpinBox(self.groupBox)
        self.grid_easting_sbox.setObjectName(u"grid_easting_sbox")
        self.grid_easting_sbox.setMinimum(-10000000)
        self.grid_easting_sbox.setMaximum(10000000)
        self.grid_easting_sbox.setValue(599709)

        self.gridLayout_3.addWidget(self.grid_easting_sbox, 0, 2, 1, 1)

        self.grid_northing_sbox = QSpinBox(self.groupBox)
        self.grid_northing_sbox.setObjectName(u"grid_northing_sbox")
        self.grid_northing_sbox.setMinimum(-10000000)
        self.grid_northing_sbox.setMaximum(10000000)
        self.grid_northing_sbox.setValue(4829107)

        self.gridLayout_3.addWidget(self.grid_northing_sbox, 1, 2, 1, 1)

        self.grid_az_sbox = QSpinBox(self.groupBox)
        self.grid_az_sbox.setObjectName(u"grid_az_sbox")
        self.grid_az_sbox.setMaximum(360)

        self.gridLayout_3.addWidget(self.grid_az_sbox, 2, 2, 1, 1)

        self.line_number_sbox = QSpinBox(self.groupBox)
        self.line_number_sbox.setObjectName(u"line_number_sbox")
        self.line_number_sbox.setMinimum(1)
        self.line_number_sbox.setMaximum(100)
        self.line_number_sbox.setValue(10)

        self.gridLayout_3.addWidget(self.line_number_sbox, 3, 2, 1, 1)

        self.line_length_sbox = QSpinBox(self.groupBox)
        self.line_length_sbox.setObjectName(u"line_length_sbox")
        self.line_length_sbox.setMinimum(1)
        self.line_length_sbox.setMaximum(10000)
        self.line_length_sbox.setSingleStep(10)
        self.line_length_sbox.setValue(1000)

        self.gridLayout_3.addWidget(self.line_length_sbox, 4, 2, 1, 1)

        self.line_spacing_sbox = QSpinBox(self.groupBox)
        self.line_spacing_sbox.setObjectName(u"line_spacing_sbox")
        self.line_spacing_sbox.setMinimum(1)
        self.line_spacing_sbox.setMaximum(10000)
        self.line_spacing_sbox.setSingleStep(10)
        self.line_spacing_sbox.setValue(100)

        self.gridLayout_3.addWidget(self.line_spacing_sbox, 5, 2, 1, 1)

        self.station_spacing_sbox = QSpinBox(self.groupBox)
        self.station_spacing_sbox.setObjectName(u"station_spacing_sbox")
        self.station_spacing_sbox.setMinimum(1)
        self.station_spacing_sbox.setMaximum(10000)
        self.station_spacing_sbox.setSingleStep(10)
        self.station_spacing_sbox.setValue(50)

        self.gridLayout_3.addWidget(self.station_spacing_sbox, 6, 2, 1, 1)


        self.verticalLayout.addWidget(self.groupBox)

        self.groupBox_4 = QGroupBox(self.frame_2)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.groupBox_4.setMaximumSize(QSize(16777215, 16777215))
        self.groupBox_4.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.gridLayout_5 = QGridLayout(self.groupBox_4)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.gps_system_cbox = QComboBox(self.groupBox_4)
        self.gps_system_cbox.setObjectName(u"gps_system_cbox")
        sizePolicy1.setHeightForWidth(self.gps_system_cbox.sizePolicy().hasHeightForWidth())
        self.gps_system_cbox.setSizePolicy(sizePolicy1)

        self.gridLayout_5.addWidget(self.gps_system_cbox, 0, 2, 1, 1)

        self.gps_zone_cbox = QComboBox(self.groupBox_4)
        self.gps_zone_cbox.setObjectName(u"gps_zone_cbox")
        self.gps_zone_cbox.setEnabled(False)

        self.gridLayout_5.addWidget(self.gps_zone_cbox, 1, 2, 1, 1)

        self.label_16 = QLabel(self.groupBox_4)
        self.label_16.setObjectName(u"label_16")
        sizePolicy2.setHeightForWidth(self.label_16.sizePolicy().hasHeightForWidth())
        self.label_16.setSizePolicy(sizePolicy2)

        self.gridLayout_5.addWidget(self.label_16, 0, 1, 1, 1)

        self.label_17 = QLabel(self.groupBox_4)
        self.label_17.setObjectName(u"label_17")

        self.gridLayout_5.addWidget(self.label_17, 1, 1, 1, 1)

        self.label_18 = QLabel(self.groupBox_4)
        self.label_18.setObjectName(u"label_18")

        self.gridLayout_5.addWidget(self.label_18, 2, 1, 1, 1)

        self.gps_datum_cbox = QComboBox(self.groupBox_4)
        self.gps_datum_cbox.setObjectName(u"gps_datum_cbox")
        self.gps_datum_cbox.setEnabled(False)

        self.gridLayout_5.addWidget(self.gps_datum_cbox, 2, 2, 1, 1)

        self.label_19 = QLabel(self.groupBox_4)
        self.label_19.setObjectName(u"label_19")

        self.gridLayout_5.addWidget(self.label_19, 4, 1, 1, 1)

        self.epsg_edit = QLineEdit(self.groupBox_4)
        self.epsg_edit.setObjectName(u"epsg_edit")
        self.epsg_edit.setEnabled(False)
        sizePolicy1.setHeightForWidth(self.epsg_edit.sizePolicy().hasHeightForWidth())
        self.epsg_edit.setSizePolicy(sizePolicy1)

        self.gridLayout_5.addWidget(self.epsg_edit, 4, 2, 1, 1)

        self.crs_rbtn = QRadioButton(self.groupBox_4)
        self.crs_rbtn.setObjectName(u"crs_rbtn")
        self.crs_rbtn.setChecked(True)

        self.gridLayout_5.addWidget(self.crs_rbtn, 1, 0, 1, 1)

        self.epsg_rbtn = QRadioButton(self.groupBox_4)
        self.epsg_rbtn.setObjectName(u"epsg_rbtn")

        self.gridLayout_5.addWidget(self.epsg_rbtn, 4, 0, 1, 1)

        self.line_3 = QFrame(self.groupBox_4)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.HLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.gridLayout_5.addWidget(self.line_3, 3, 0, 1, 3)


        self.verticalLayout.addWidget(self.groupBox_4)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.splitter.addWidget(self.frame_2)
        self.plan_view = PlotWidget(self.splitter)
        self.plan_view.setObjectName(u"plan_view")
        sizePolicy3 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        sizePolicy3.setHorizontalStretch(1)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.plan_view.sizePolicy().hasHeightForWidth())
        self.plan_view.setSizePolicy(sizePolicy3)
        self.plan_view.setMinimumSize(QSize(450, 300))
        self.plan_view.setFrameShape(QFrame.Box)
        self.plan_view.setFrameShadow(QFrame.Sunken)
        self.splitter.addWidget(self.plan_view)

        self.horizontalLayout.addWidget(self.splitter)

        GridPlanner.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(GridPlanner)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1126, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")
        GridPlanner.setMenuBar(self.menubar)
        self.status_bar = QStatusBar(GridPlanner)
        self.status_bar.setObjectName(u"status_bar")
        GridPlanner.setStatusBar(self.status_bar)
        QWidget.setTabOrder(self.loop_name_edit, self.grid_name_edit)
        QWidget.setTabOrder(self.grid_name_edit, self.plan_view)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menuFile.addAction(self.actionSave_as_KMZ)
        self.menuFile.addAction(self.actionSave_as_GPX)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionCopy_Grid_to_Clipboard)
        self.menuFile.addAction(self.actionCopy_Loop_to_Clipboard)
        self.menuView.addAction(self.view_map_action)

        self.retranslateUi(GridPlanner)

        self.gps_system_cbox.setCurrentIndex(-1)


        QMetaObject.connectSlotsByName(GridPlanner)
    # setupUi

    def retranslateUi(self, GridPlanner):
        GridPlanner.setWindowTitle(QCoreApplication.translate("GridPlanner", u"MainWindow", None))
        self.actionSave_as_KMZ.setText(QCoreApplication.translate("GridPlanner", u"Save as KMZ...", None))
        self.actionSave_as_GPX.setText(QCoreApplication.translate("GridPlanner", u"Save as GPX...", None))
        self.view_map_action.setText(QCoreApplication.translate("GridPlanner", u"Map", None))
        self.actionCopy_Grid_to_Clipboard.setText(QCoreApplication.translate("GridPlanner", u"Copy Grid to Clipboard", None))
        self.actionCopy_Loop_to_Clipboard.setText(QCoreApplication.translate("GridPlanner", u"Copy Loop to Clipboard", None))
        self.tx_loop_gbox.setTitle(QCoreApplication.translate("GridPlanner", u"Tx Loop", None))
        self.label_4.setText(QCoreApplication.translate("GridPlanner", u"Angle", None))
        self.label_3.setText(QCoreApplication.translate("GridPlanner", u"Height", None))
        self.label_2.setText(QCoreApplication.translate("GridPlanner", u"Width", None))
        self.label_12.setText(QCoreApplication.translate("GridPlanner", u"Name", None))
        self.loop_name_edit.setPlaceholderText(QCoreApplication.translate("GridPlanner", u"(Optional)", None))
#if QT_CONFIG(tooltip)
        self.include_loop_cbox.setToolTip(QCoreApplication.translate("GridPlanner", u"Include the loop when saving a KMZ or GPX file", None))
#endif // QT_CONFIG(tooltip)
        self.include_loop_cbox.setText(QCoreApplication.translate("GridPlanner", u"Include Loop on Save", None))
        self.loop_height_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"m", None))
        self.loop_width_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"m", None))
        self.loop_angle_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"\u00b0", None))
        self.groupBox.setTitle(QCoreApplication.translate("GridPlanner", u"Grid", None))
        self.label_13.setText(QCoreApplication.translate("GridPlanner", u"Name", None))
        self.grid_name_edit.setPlaceholderText(QCoreApplication.translate("GridPlanner", u"(Optional)", None))
        self.label_14.setText(QCoreApplication.translate("GridPlanner", u"Line\n"
"Length", None))
        self.label_10.setText(QCoreApplication.translate("GridPlanner", u"Station\n"
"Spacing", None))
        self.label_9.setText(QCoreApplication.translate("GridPlanner", u"Azimuth", None))
        self.label.setText(QCoreApplication.translate("GridPlanner", u"Easting ", None))
        self.label_5.setText(QCoreApplication.translate("GridPlanner", u"Northing", None))
        self.label_11.setText(QCoreApplication.translate("GridPlanner", u"Line\n"
"Spacing", None))
        self.label_15.setText(QCoreApplication.translate("GridPlanner", u"Number\n"
"of Lines", None))
        self.grid_easting_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"m", None))
        self.grid_northing_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"m", None))
        self.grid_az_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"\u00b0", None))
        self.line_length_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"m", None))
        self.line_spacing_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"m", None))
        self.station_spacing_sbox.setSuffix(QCoreApplication.translate("GridPlanner", u"m", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("GridPlanner", u"Coordinate System", None))
        self.label_16.setText(QCoreApplication.translate("GridPlanner", u"System:", None))
        self.label_17.setText(QCoreApplication.translate("GridPlanner", u"Zone:", None))
        self.label_18.setText(QCoreApplication.translate("GridPlanner", u"Datum:", None))
        self.label_19.setText(QCoreApplication.translate("GridPlanner", u"EPSG:", None))
        self.crs_rbtn.setText("")
        self.epsg_rbtn.setText("")
        self.menuFile.setTitle(QCoreApplication.translate("GridPlanner", u"File", None))
        self.menuView.setTitle(QCoreApplication.translate("GridPlanner", u"View", None))
    # retranslateUi

