# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'pem_info_widget.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_PEMInfoWidget(object):
    def setupUi(self, PEMInfoWidget):
        if not PEMInfoWidget.objectName():
            PEMInfoWidget.setObjectName(u"PEMInfoWidget")
        PEMInfoWidget.resize(780, 814)
        sizePolicy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(PEMInfoWidget.sizePolicy().hasHeightForWidth())
        PEMInfoWidget.setSizePolicy(sizePolicy)
        PEMInfoWidget.setMinimumSize(QSize(0, 0))
        self.gridLayout = QGridLayout(PEMInfoWidget)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget(PEMInfoWidget)
        self.tabs.setObjectName(u"tabs")
        self.tabs.setEnabled(True)
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.tabs.sizePolicy().hasHeightForWidth())
        self.tabs.setSizePolicy(sizePolicy1)
        self.tabs.setMinimumSize(QSize(0, 0))
        self.tabs.setMaximumSize(QSize(16777215, 16777215))
        font = QFont()
        font.setFamily(u"Century Gothic")
        font.setPointSize(9)
        self.tabs.setFont(font)
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setTabShape(QTabWidget.Rounded)
        self.info_tab = QWidget()
        self.info_tab.setObjectName(u"info_tab")
        self.gridLayout_2 = QGridLayout(self.info_tab)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.info_table = QTableWidget(self.info_tab)
        if (self.info_table.columnCount() < 2):
            self.info_table.setColumnCount(2)
        font1 = QFont()
        font1.setBold(False)
        font1.setWeight(50)
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setTextAlignment(Qt.AlignLeading|Qt.AlignVCenter);
        __qtablewidgetitem.setFont(font1);
        self.info_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.info_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        self.info_table.setObjectName(u"info_table")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.info_table.sizePolicy().hasHeightForWidth())
        self.info_table.setSizePolicy(sizePolicy2)
        self.info_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.info_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.info_table.setShowGrid(True)
        self.info_table.setWordWrap(False)
        self.info_table.horizontalHeader().setVisible(False)
        self.info_table.horizontalHeader().setMinimumSectionSize(120)
        self.info_table.horizontalHeader().setStretchLastSection(True)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.verticalHeader().setMinimumSectionSize(0)
        self.info_table.verticalHeader().setDefaultSectionSize(23)
        self.info_table.verticalHeader().setStretchLastSection(False)

        self.gridLayout_2.addWidget(self.info_table, 0, 0, 1, 1)

        self.tabs.addTab(self.info_tab, "")
        self.loop_gps_tab = QWidget()
        self.loop_gps_tab.setObjectName(u"loop_gps_tab")
        self.gridLayout_4 = QGridLayout(self.loop_gps_tab)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.frame_3 = QFrame(self.loop_gps_tab)
        self.frame_3.setObjectName(u"frame_3")
        sizePolicy3 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.frame_3.sizePolicy().hasHeightForWidth())
        self.frame_3.setSizePolicy(sizePolicy3)
        self.frame_3.setMinimumSize(QSize(400, 0))
        self.frame_3.setMaximumSize(QSize(16777215, 16777215))
        self.frame_3.setFrameShape(QFrame.Box)
        self.frame_3.setFrameShadow(QFrame.Sunken)
        self.gridLayout_8 = QGridLayout(self.frame_3)
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.gridLayout_8.setContentsMargins(6, 6, 6, 6)
        self.share_loop_gps_btn = QPushButton(self.frame_3)
        self.share_loop_gps_btn.setObjectName(u"share_loop_gps_btn")

        self.gridLayout_8.addWidget(self.share_loop_gps_btn, 2, 3, 1, 1)

        self.export_loop_gps_btn = QPushButton(self.frame_3)
        self.export_loop_gps_btn.setObjectName(u"export_loop_gps_btn")

        self.gridLayout_8.addWidget(self.export_loop_gps_btn, 1, 3, 1, 1)

        self.edit_loop_btn = QPushButton(self.frame_3)
        self.edit_loop_btn.setObjectName(u"edit_loop_btn")

        self.gridLayout_8.addWidget(self.edit_loop_btn, 2, 1, 1, 1)

        self.open_loop_gps_btn = QPushButton(self.frame_3)
        self.open_loop_gps_btn.setObjectName(u"open_loop_gps_btn")
        sizePolicy4 = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.open_loop_gps_btn.sizePolicy().hasHeightForWidth())
        self.open_loop_gps_btn.setSizePolicy(sizePolicy4)

        self.gridLayout_8.addWidget(self.open_loop_gps_btn, 1, 1, 1, 1)

        self.shift_elevation_spinbox = QSpinBox(self.frame_3)
        self.shift_elevation_spinbox.setObjectName(u"shift_elevation_spinbox")
        self.shift_elevation_spinbox.setMinimum(-10000)
        self.shift_elevation_spinbox.setMaximum(10000)

        self.gridLayout_8.addWidget(self.shift_elevation_spinbox, 2, 4, 1, 1)

        self.shiftElevationLabel = QLabel(self.frame_3)
        self.shiftElevationLabel.setObjectName(u"shiftElevationLabel")

        self.gridLayout_8.addWidget(self.shiftElevationLabel, 1, 4, 1, 1)


        self.gridLayout_4.addWidget(self.frame_3, 2, 0, 1, 3)

        self.loop_table = QTableWidget(self.loop_gps_tab)
        if (self.loop_table.columnCount() < 4):
            self.loop_table.setColumnCount(4)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.loop_table.setHorizontalHeaderItem(0, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.loop_table.setHorizontalHeaderItem(1, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.loop_table.setHorizontalHeaderItem(2, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.loop_table.setHorizontalHeaderItem(3, __qtablewidgetitem5)
        self.loop_table.setObjectName(u"loop_table")
        sizePolicy2.setHeightForWidth(self.loop_table.sizePolicy().hasHeightForWidth())
        self.loop_table.setSizePolicy(sizePolicy2)
        self.loop_table.setMinimumSize(QSize(400, 0))
        self.loop_table.setMaximumSize(QSize(16777215, 16777215))
        self.loop_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.loop_table.setShowGrid(False)
        self.loop_table.horizontalHeader().setHighlightSections(False)
        self.loop_table.verticalHeader().setVisible(False)

        self.gridLayout_4.addWidget(self.loop_table, 1, 0, 1, 3)

        self.tabs.addTab(self.loop_gps_tab, "")
        self.station_gps_tab = QWidget()
        self.station_gps_tab.setObjectName(u"station_gps_tab")
        self.gridLayout_3 = QGridLayout(self.station_gps_tab)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.frame_6 = QFrame(self.station_gps_tab)
        self.frame_6.setObjectName(u"frame_6")
        sizePolicy3.setHeightForWidth(self.frame_6.sizePolicy().hasHeightForWidth())
        self.frame_6.setSizePolicy(sizePolicy3)
        self.frame_6.setMinimumSize(QSize(400, 0))
        self.frame_6.setMaximumSize(QSize(16777215, 250))
        self.frame_6.setFrameShape(QFrame.Box)
        self.frame_6.setFrameShadow(QFrame.Sunken)
        self.horizontalLayout = QHBoxLayout(self.frame_6)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(self.frame_6)
        self.frame.setObjectName(u"frame")
        sizePolicy5 = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy5)
        self.frame.setMinimumSize(QSize(133, 0))
        self.frame.setMaximumSize(QSize(16777215, 16777215))
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame)
        self.verticalLayout_2.setSpacing(6)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(9, 9, 9, 9)
        self.shiftStationLabel = QLabel(self.frame)
        self.shiftStationLabel.setObjectName(u"shiftStationLabel")
        sizePolicy3.setHeightForWidth(self.shiftStationLabel.sizePolicy().hasHeightForWidth())
        self.shiftStationLabel.setSizePolicy(sizePolicy3)

        self.verticalLayout_2.addWidget(self.shiftStationLabel)

        self.shiftStationGPSSpinbox = QSpinBox(self.frame)
        self.shiftStationGPSSpinbox.setObjectName(u"shiftStationGPSSpinbox")
        sizePolicy6 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(0)
        sizePolicy6.setHeightForWidth(self.shiftStationGPSSpinbox.sizePolicy().hasHeightForWidth())
        self.shiftStationGPSSpinbox.setSizePolicy(sizePolicy6)
        self.shiftStationGPSSpinbox.setMinimum(-1000000000)
        self.shiftStationGPSSpinbox.setMaximum(1000000000)
        self.shiftStationGPSSpinbox.setSingleStep(5)

        self.verticalLayout_2.addWidget(self.shiftStationGPSSpinbox)

        self.line_6 = QFrame(self.frame)
        self.line_6.setObjectName(u"line_6")
        self.line_6.setFrameShape(QFrame.HLine)
        self.line_6.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_2.addWidget(self.line_6)

        self.open_station_gps_btn = QPushButton(self.frame)
        self.open_station_gps_btn.setObjectName(u"open_station_gps_btn")
        sizePolicy6.setHeightForWidth(self.open_station_gps_btn.sizePolicy().hasHeightForWidth())
        self.open_station_gps_btn.setSizePolicy(sizePolicy6)

        self.verticalLayout_2.addWidget(self.open_station_gps_btn)

        self.edit_line_btn = QPushButton(self.frame)
        self.edit_line_btn.setObjectName(u"edit_line_btn")
        sizePolicy6.setHeightForWidth(self.edit_line_btn.sizePolicy().hasHeightForWidth())
        self.edit_line_btn.setSizePolicy(sizePolicy6)

        self.verticalLayout_2.addWidget(self.edit_line_btn)

        self.line = QFrame(self.frame)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_2.addWidget(self.line)

        self.export_station_gps_btn = QPushButton(self.frame)
        self.export_station_gps_btn.setObjectName(u"export_station_gps_btn")
        sizePolicy6.setHeightForWidth(self.export_station_gps_btn.sizePolicy().hasHeightForWidth())
        self.export_station_gps_btn.setSizePolicy(sizePolicy6)

        self.verticalLayout_2.addWidget(self.export_station_gps_btn)

        self.share_line_gps_btn = QPushButton(self.frame)
        self.share_line_gps_btn.setObjectName(u"share_line_gps_btn")

        self.verticalLayout_2.addWidget(self.share_line_gps_btn)


        self.horizontalLayout.addWidget(self.frame)

        self.line_2 = QFrame(self.frame_6)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.VLine)
        self.line_2.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout.addWidget(self.line_2)

        self.frame_5 = QFrame(self.frame_6)
        self.frame_5.setObjectName(u"frame_5")
        sizePolicy5.setHeightForWidth(self.frame_5.sizePolicy().hasHeightForWidth())
        self.frame_5.setSizePolicy(sizePolicy5)
        self.frame_5.setMinimumSize(QSize(133, 0))
        self.frame_5.setMaximumSize(QSize(16777215, 16777215))
        self.frame_5.setFrameShape(QFrame.NoFrame)
        self.frame_5.setFrameShadow(QFrame.Raised)
        self.verticalLayout_6 = QVBoxLayout(self.frame_5)
        self.verticalLayout_6.setSpacing(6)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.label_2 = QLabel(self.frame_5)
        self.label_2.setObjectName(u"label_2")

        self.verticalLayout_6.addWidget(self.label_2)

        self.lcdDistance = QLCDNumber(self.frame_5)
        self.lcdDistance.setObjectName(u"lcdDistance")
        sizePolicy1.setHeightForWidth(self.lcdDistance.sizePolicy().hasHeightForWidth())
        self.lcdDistance.setSizePolicy(sizePolicy1)
        self.lcdDistance.setMinimumSize(QSize(0, 22))
        self.lcdDistance.setFrameShape(QFrame.Box)
        self.lcdDistance.setFrameShadow(QFrame.Sunken)
        self.lcdDistance.setLineWidth(1)
        self.lcdDistance.setMidLineWidth(0)
        self.lcdDistance.setSmallDecimalPoint(False)
        self.lcdDistance.setDigitCount(7)
        self.lcdDistance.setSegmentStyle(QLCDNumber.Flat)

        self.verticalLayout_6.addWidget(self.lcdDistance)

        self.line_9 = QFrame(self.frame_5)
        self.line_9.setObjectName(u"line_9")
        self.line_9.setFrameShape(QFrame.HLine)
        self.line_9.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_6.addWidget(self.line_9)

        self.flip_station_signs_button = QPushButton(self.frame_5)
        self.flip_station_signs_button.setObjectName(u"flip_station_signs_button")
        sizePolicy6.setHeightForWidth(self.flip_station_signs_button.sizePolicy().hasHeightForWidth())
        self.flip_station_signs_button.setSizePolicy(sizePolicy6)

        self.verticalLayout_6.addWidget(self.flip_station_signs_button)

        self.flip_station_numbers_button = QPushButton(self.frame_5)
        self.flip_station_numbers_button.setObjectName(u"flip_station_numbers_button")
        sizePolicy6.setHeightForWidth(self.flip_station_numbers_button.sizePolicy().hasHeightForWidth())
        self.flip_station_numbers_button.setSizePolicy(sizePolicy6)

        self.verticalLayout_6.addWidget(self.flip_station_numbers_button)

        self.line_5 = QFrame(self.frame_5)
        self.line_5.setObjectName(u"line_5")
        self.line_5.setFrameShape(QFrame.HLine)
        self.line_5.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_6.addWidget(self.line_5)

        self.stations_from_data_btn = QPushButton(self.frame_5)
        self.stations_from_data_btn.setObjectName(u"stations_from_data_btn")
        sizePolicy6.setHeightForWidth(self.stations_from_data_btn.sizePolicy().hasHeightForWidth())
        self.stations_from_data_btn.setSizePolicy(sizePolicy6)

        self.verticalLayout_6.addWidget(self.stations_from_data_btn)

        self.cullStationGPSButton = QPushButton(self.frame_5)
        self.cullStationGPSButton.setObjectName(u"cullStationGPSButton")
        sizePolicy6.setHeightForWidth(self.cullStationGPSButton.sizePolicy().hasHeightForWidth())
        self.cullStationGPSButton.setSizePolicy(sizePolicy6)

        self.verticalLayout_6.addWidget(self.cullStationGPSButton)


        self.horizontalLayout.addWidget(self.frame_5)

        self.line_4 = QFrame(self.frame_6)
        self.line_4.setObjectName(u"line_4")
        self.line_4.setFrameShape(QFrame.VLine)
        self.line_4.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout.addWidget(self.line_4)

        self.frame_4 = QFrame(self.frame_6)
        self.frame_4.setObjectName(u"frame_4")
        sizePolicy3.setHeightForWidth(self.frame_4.sizePolicy().hasHeightForWidth())
        self.frame_4.setSizePolicy(sizePolicy3)
        self.frame_4.setMaximumSize(QSize(16777215, 16777215))
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame_4)
        self.verticalLayout_4.setSpacing(6)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(9, 9, 9, 9)
        self.label_4 = QLabel(self.frame_4)
        self.label_4.setObjectName(u"label_4")

        self.verticalLayout_4.addWidget(self.label_4)

        self.missing_gps_list = QListWidget(self.frame_4)
        self.missing_gps_list.setObjectName(u"missing_gps_list")
        sizePolicy7 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        sizePolicy7.setHorizontalStretch(0)
        sizePolicy7.setVerticalStretch(0)
        sizePolicy7.setHeightForWidth(self.missing_gps_list.sizePolicy().hasHeightForWidth())
        self.missing_gps_list.setSizePolicy(sizePolicy7)
        self.missing_gps_list.setMaximumSize(QSize(16777215, 160))

        self.verticalLayout_4.addWidget(self.missing_gps_list)


        self.horizontalLayout.addWidget(self.frame_4)


        self.gridLayout_3.addWidget(self.frame_6, 19, 1, 1, 2)

        self.line_table = QTableWidget(self.station_gps_tab)
        if (self.line_table.columnCount() < 5):
            self.line_table.setColumnCount(5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.line_table.setHorizontalHeaderItem(0, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.line_table.setHorizontalHeaderItem(1, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.line_table.setHorizontalHeaderItem(2, __qtablewidgetitem8)
        __qtablewidgetitem9 = QTableWidgetItem()
        self.line_table.setHorizontalHeaderItem(3, __qtablewidgetitem9)
        __qtablewidgetitem10 = QTableWidgetItem()
        self.line_table.setHorizontalHeaderItem(4, __qtablewidgetitem10)
        self.line_table.setObjectName(u"line_table")
        sizePolicy2.setHeightForWidth(self.line_table.sizePolicy().hasHeightForWidth())
        self.line_table.setSizePolicy(sizePolicy2)
        self.line_table.setMinimumSize(QSize(400, 0))
        self.line_table.setMaximumSize(QSize(16777215, 16777215))
        self.line_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.line_table.setShowGrid(False)
        self.line_table.horizontalHeader().setHighlightSections(False)
        self.line_table.verticalHeader().setVisible(False)

        self.gridLayout_3.addWidget(self.line_table, 0, 1, 19, 2)

        self.tabs.addTab(self.station_gps_tab, "")
        self.geometry_tab = QWidget()
        self.geometry_tab.setObjectName(u"geometry_tab")
        self.gridLayout_5 = QGridLayout(self.geometry_tab)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.frame_9 = QFrame(self.geometry_tab)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setMinimumSize(QSize(400, 0))
        self.frame_9.setFrameShape(QFrame.Box)
        self.frame_9.setFrameShadow(QFrame.Sunken)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_9)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(6, 6, 6, 6)
        self.add_segments_btn = QPushButton(self.frame_9)
        self.add_segments_btn.setObjectName(u"add_segments_btn")

        self.horizontalLayout_3.addWidget(self.add_segments_btn)

        self.export_segments_btn = QPushButton(self.frame_9)
        self.export_segments_btn.setObjectName(u"export_segments_btn")

        self.horizontalLayout_3.addWidget(self.export_segments_btn)

        self.share_segments_btn = QPushButton(self.frame_9)
        self.share_segments_btn.setObjectName(u"share_segments_btn")

        self.horizontalLayout_3.addWidget(self.share_segments_btn)


        self.gridLayout_5.addWidget(self.frame_9, 5, 0, 1, 1)

        self.label_5 = QLabel(self.geometry_tab)
        self.label_5.setObjectName(u"label_5")
        font2 = QFont()
        font2.setFamily(u"Century Gothic")
        font2.setPointSize(9)
        font2.setBold(True)
        font2.setWeight(75)
        self.label_5.setFont(font2)

        self.gridLayout_5.addWidget(self.label_5, 0, 0, 1, 1, Qt.AlignHCenter)

        self.segments_table = QTableWidget(self.geometry_tab)
        if (self.segments_table.columnCount() < 5):
            self.segments_table.setColumnCount(5)
        __qtablewidgetitem11 = QTableWidgetItem()
        self.segments_table.setHorizontalHeaderItem(0, __qtablewidgetitem11)
        __qtablewidgetitem12 = QTableWidgetItem()
        self.segments_table.setHorizontalHeaderItem(1, __qtablewidgetitem12)
        __qtablewidgetitem13 = QTableWidgetItem()
        self.segments_table.setHorizontalHeaderItem(2, __qtablewidgetitem13)
        __qtablewidgetitem14 = QTableWidgetItem()
        self.segments_table.setHorizontalHeaderItem(3, __qtablewidgetitem14)
        __qtablewidgetitem15 = QTableWidgetItem()
        self.segments_table.setHorizontalHeaderItem(4, __qtablewidgetitem15)
        self.segments_table.setObjectName(u"segments_table")
        sizePolicy2.setHeightForWidth(self.segments_table.sizePolicy().hasHeightForWidth())
        self.segments_table.setSizePolicy(sizePolicy2)
        self.segments_table.setMinimumSize(QSize(400, 0))
        self.segments_table.setMaximumSize(QSize(16777215, 16777215))
        self.segments_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.segments_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.segments_table.setShowGrid(False)
        self.segments_table.horizontalHeader().setHighlightSections(False)
        self.segments_table.verticalHeader().setVisible(False)

        self.gridLayout_5.addWidget(self.segments_table, 4, 0, 1, 1)

        self.label_6 = QLabel(self.geometry_tab)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setFont(font2)

        self.gridLayout_5.addWidget(self.label_6, 3, 0, 1, 1, Qt.AlignHCenter)

        self.frame_10 = QFrame(self.geometry_tab)
        self.frame_10.setObjectName(u"frame_10")
        self.frame_10.setMinimumSize(QSize(400, 0))
        self.frame_10.setFrameShape(QFrame.Box)
        self.frame_10.setFrameShadow(QFrame.Sunken)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_10)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(6, 6, 6, 6)
        self.open_collar_gps_btn = QPushButton(self.frame_10)
        self.open_collar_gps_btn.setObjectName(u"open_collar_gps_btn")

        self.horizontalLayout_4.addWidget(self.open_collar_gps_btn)

        self.export_collar_gps_btn = QPushButton(self.frame_10)
        self.export_collar_gps_btn.setObjectName(u"export_collar_gps_btn")

        self.horizontalLayout_4.addWidget(self.export_collar_gps_btn)

        self.share_collar_gps_btn = QPushButton(self.frame_10)
        self.share_collar_gps_btn.setObjectName(u"share_collar_gps_btn")

        self.horizontalLayout_4.addWidget(self.share_collar_gps_btn)


        self.gridLayout_5.addWidget(self.frame_10, 2, 0, 1, 1)

        self.collar_table = QTableWidget(self.geometry_tab)
        if (self.collar_table.columnCount() < 4):
            self.collar_table.setColumnCount(4)
        __qtablewidgetitem16 = QTableWidgetItem()
        self.collar_table.setHorizontalHeaderItem(0, __qtablewidgetitem16)
        __qtablewidgetitem17 = QTableWidgetItem()
        self.collar_table.setHorizontalHeaderItem(1, __qtablewidgetitem17)
        __qtablewidgetitem18 = QTableWidgetItem()
        self.collar_table.setHorizontalHeaderItem(2, __qtablewidgetitem18)
        __qtablewidgetitem19 = QTableWidgetItem()
        self.collar_table.setHorizontalHeaderItem(3, __qtablewidgetitem19)
        if (self.collar_table.rowCount() < 1):
            self.collar_table.setRowCount(1)
        __qtablewidgetitem20 = QTableWidgetItem()
        __qtablewidgetitem20.setTextAlignment(Qt.AlignCenter);
        self.collar_table.setItem(0, 0, __qtablewidgetitem20)
        __qtablewidgetitem21 = QTableWidgetItem()
        __qtablewidgetitem21.setTextAlignment(Qt.AlignCenter);
        self.collar_table.setItem(0, 1, __qtablewidgetitem21)
        __qtablewidgetitem22 = QTableWidgetItem()
        __qtablewidgetitem22.setTextAlignment(Qt.AlignCenter);
        self.collar_table.setItem(0, 2, __qtablewidgetitem22)
        __qtablewidgetitem23 = QTableWidgetItem()
        __qtablewidgetitem23.setTextAlignment(Qt.AlignCenter);
        self.collar_table.setItem(0, 3, __qtablewidgetitem23)
        self.collar_table.setObjectName(u"collar_table")
        sizePolicy2.setHeightForWidth(self.collar_table.sizePolicy().hasHeightForWidth())
        self.collar_table.setSizePolicy(sizePolicy2)
        self.collar_table.setMinimumSize(QSize(0, 0))
        self.collar_table.setMaximumSize(QSize(16777215, 60))
        self.collar_table.setFrameShape(QFrame.StyledPanel)
        self.collar_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.collar_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.collar_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.collar_table.setShowGrid(False)
        self.collar_table.setCornerButtonEnabled(True)
        self.collar_table.setRowCount(1)
        self.collar_table.horizontalHeader().setHighlightSections(False)
        self.collar_table.verticalHeader().setVisible(False)
        self.collar_table.verticalHeader().setCascadingSectionResizes(False)
        self.collar_table.verticalHeader().setDefaultSectionSize(30)

        self.gridLayout_5.addWidget(self.collar_table, 1, 0, 1, 1)

        self.tabs.addTab(self.geometry_tab, "")
        self.ri_tab = QWidget()
        self.ri_tab.setObjectName(u"ri_tab")
        self.gridLayout_7 = QGridLayout(self.ri_tab)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.ri_table = QTableWidget(self.ri_tab)
        self.ri_table.setObjectName(u"ri_table")
        self.ri_table.setAutoScroll(False)
        self.ri_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.gridLayout_7.addWidget(self.ri_table, 0, 0, 1, 1)

        self.tabs.addTab(self.ri_tab, "")

        self.gridLayout.addWidget(self.tabs, 1, 0, 1, 1)


        self.retranslateUi(PEMInfoWidget)

        self.tabs.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(PEMInfoWidget)
    # setupUi

    def retranslateUi(self, PEMInfoWidget):
        PEMInfoWidget.setWindowTitle(QCoreApplication.translate("PEMInfoWidget", u"Form", None))
        ___qtablewidgetitem = self.info_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("PEMInfoWidget", u"Keys", None));
        ___qtablewidgetitem1 = self.info_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("PEMInfoWidget", u"Values", None));
        self.tabs.setTabText(self.tabs.indexOf(self.info_tab), QCoreApplication.translate("PEMInfoWidget", u"Info", None))
        self.share_loop_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Share Loop", None))
        self.export_loop_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Export Loop", None))
        self.edit_loop_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"View Loop", None))
        self.open_loop_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Open File", None))
        self.shiftElevationLabel.setText(QCoreApplication.translate("PEMInfoWidget", u"Shift Elevation:", None))
        ___qtablewidgetitem2 = self.loop_table.horizontalHeaderItem(0)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("PEMInfoWidget", u"Easting", None));
        ___qtablewidgetitem3 = self.loop_table.horizontalHeaderItem(1)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("PEMInfoWidget", u"Northing", None));
        ___qtablewidgetitem4 = self.loop_table.horizontalHeaderItem(2)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("PEMInfoWidget", u"Elevation", None));
        ___qtablewidgetitem5 = self.loop_table.horizontalHeaderItem(3)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("PEMInfoWidget", u"Unit", None));
        self.tabs.setTabText(self.tabs.indexOf(self.loop_gps_tab), QCoreApplication.translate("PEMInfoWidget", u"Loop GPS", None))
        self.shiftStationLabel.setText(QCoreApplication.translate("PEMInfoWidget", u"Shift Stations:", None))
        self.open_station_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Open File", None))
        self.edit_line_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"View Line", None))
        self.export_station_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Export GPS", None))
#if QT_CONFIG(tooltip)
        self.share_line_gps_btn.setToolTip(QCoreApplication.translate("PEMInfoWidget", u"Share this GPS with all other opened surface files", None))
#endif // QT_CONFIG(tooltip)
        self.share_line_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Share Line", None))
        self.label_2.setText(QCoreApplication.translate("PEMInfoWidget", u"Distance:", None))
        self.flip_station_signs_button.setText(QCoreApplication.translate("PEMInfoWidget", u"+/- Stations", None))
#if QT_CONFIG(tooltip)
        self.flip_station_numbers_button.setToolTip(QCoreApplication.translate("PEMInfoWidget", u"Reverse order of the station GPS", None))
#endif // QT_CONFIG(tooltip)
        self.flip_station_numbers_button.setText(QCoreApplication.translate("PEMInfoWidget", u"\u2191\u2193 Stations", None))
#if QT_CONFIG(tooltip)
        self.stations_from_data_btn.setToolTip(QCoreApplication.translate("PEMInfoWidget", u"Generate station numbers based on the stations in the EM data", None))
#endif // QT_CONFIG(tooltip)
        self.stations_from_data_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Generate Stations", None))
#if QT_CONFIG(tooltip)
        self.cullStationGPSButton.setToolTip(QCoreApplication.translate("PEMInfoWidget", u"Remove GPS stations for which there is no EM data", None))
#endif // QT_CONFIG(tooltip)
        self.cullStationGPSButton.setText(QCoreApplication.translate("PEMInfoWidget", u"Cull Stations", None))
        self.label_4.setText(QCoreApplication.translate("PEMInfoWidget", u"Missing Stations:", None))
        ___qtablewidgetitem6 = self.line_table.horizontalHeaderItem(0)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("PEMInfoWidget", u"Easting", None));
        ___qtablewidgetitem7 = self.line_table.horizontalHeaderItem(1)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("PEMInfoWidget", u"Northing", None));
        ___qtablewidgetitem8 = self.line_table.horizontalHeaderItem(2)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("PEMInfoWidget", u"Elevation", None));
        ___qtablewidgetitem9 = self.line_table.horizontalHeaderItem(3)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("PEMInfoWidget", u"Unit", None));
        ___qtablewidgetitem10 = self.line_table.horizontalHeaderItem(4)
        ___qtablewidgetitem10.setText(QCoreApplication.translate("PEMInfoWidget", u"Station", None));
        self.tabs.setTabText(self.tabs.indexOf(self.station_gps_tab), QCoreApplication.translate("PEMInfoWidget", u"Station GPS", None))
        self.add_segments_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Add Segments", None))
        self.export_segments_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Export Segments", None))
        self.share_segments_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Share Segments", None))
        self.label_5.setText(QCoreApplication.translate("PEMInfoWidget", u"Collar", None))
        ___qtablewidgetitem11 = self.segments_table.horizontalHeaderItem(0)
        ___qtablewidgetitem11.setText(QCoreApplication.translate("PEMInfoWidget", u"Azimuth", None));
        ___qtablewidgetitem12 = self.segments_table.horizontalHeaderItem(1)
        ___qtablewidgetitem12.setText(QCoreApplication.translate("PEMInfoWidget", u"Dip", None));
        ___qtablewidgetitem13 = self.segments_table.horizontalHeaderItem(2)
        ___qtablewidgetitem13.setText(QCoreApplication.translate("PEMInfoWidget", u"Segment\n"
"Length", None));
        ___qtablewidgetitem14 = self.segments_table.horizontalHeaderItem(3)
        ___qtablewidgetitem14.setText(QCoreApplication.translate("PEMInfoWidget", u"Units", None));
        ___qtablewidgetitem15 = self.segments_table.horizontalHeaderItem(4)
        ___qtablewidgetitem15.setText(QCoreApplication.translate("PEMInfoWidget", u"Depth", None));
        self.label_6.setText(QCoreApplication.translate("PEMInfoWidget", u"Segments", None))
        self.open_collar_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Open File", None))
        self.export_collar_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Export Collar", None))
        self.share_collar_gps_btn.setText(QCoreApplication.translate("PEMInfoWidget", u"Share Collar", None))
        ___qtablewidgetitem16 = self.collar_table.horizontalHeaderItem(0)
        ___qtablewidgetitem16.setText(QCoreApplication.translate("PEMInfoWidget", u"Easting", None));
        ___qtablewidgetitem17 = self.collar_table.horizontalHeaderItem(1)
        ___qtablewidgetitem17.setText(QCoreApplication.translate("PEMInfoWidget", u"Northing", None));
        ___qtablewidgetitem18 = self.collar_table.horizontalHeaderItem(2)
        ___qtablewidgetitem18.setText(QCoreApplication.translate("PEMInfoWidget", u"Elevation", None));
        ___qtablewidgetitem19 = self.collar_table.horizontalHeaderItem(3)
        ___qtablewidgetitem19.setText(QCoreApplication.translate("PEMInfoWidget", u"Units", None));

        __sortingEnabled = self.collar_table.isSortingEnabled()
        self.collar_table.setSortingEnabled(False)
        self.collar_table.setSortingEnabled(__sortingEnabled)

        self.tabs.setTabText(self.tabs.indexOf(self.geometry_tab), QCoreApplication.translate("PEMInfoWidget", u"Hole Geometry", None))
        self.tabs.setTabText(self.tabs.indexOf(self.ri_tab), QCoreApplication.translate("PEMInfoWidget", u"RI File", None))
    # retranslateUi
