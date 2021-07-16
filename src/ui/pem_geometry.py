# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'pem_geometry.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_PEMGeometry(object):
    def setupUi(self, PEMGeometry):
        if not PEMGeometry.objectName():
            PEMGeometry.setObjectName(u"PEMGeometry")
        PEMGeometry.resize(943, 669)
        PEMGeometry.setAcceptDrops(True)
        self.actionOpen_Geometry_File = QAction(PEMGeometry)
        self.actionOpen_Geometry_File.setObjectName(u"actionOpen_Geometry_File")
        self.actionPolar_Plot = QAction(PEMGeometry)
        self.actionPolar_Plot.setObjectName(u"actionPolar_Plot")
        self.actionAllow_Negative_Azimuth = QAction(PEMGeometry)
        self.actionAllow_Negative_Azimuth.setObjectName(u"actionAllow_Negative_Azimuth")
        self.actionAllow_Negative_Azimuth.setCheckable(True)
        self.actionAllow_Negative_Azimuth.setChecked(True)
        self.actionCopy_Screenshot = QAction(PEMGeometry)
        self.actionCopy_Screenshot.setObjectName(u"actionCopy_Screenshot")
        self.actionSave_Screenshot = QAction(PEMGeometry)
        self.actionSave_Screenshot.setObjectName(u"actionSave_Screenshot")
        self.centralwidget = QWidget(PEMGeometry)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName(u"frame")
        sizePolicy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setFrameShape(QFrame.Box)
        self.frame.setFrameShadow(QFrame.Sunken)
        self.verticalLayout = QVBoxLayout(self.frame)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label = QLabel(self.frame)
        self.label.setObjectName(u"label")

        self.verticalLayout.addWidget(self.label)

        self.mag_dec_sbox = QDoubleSpinBox(self.frame)
        self.mag_dec_sbox.setObjectName(u"mag_dec_sbox")
        self.mag_dec_sbox.setEnabled(False)
        self.mag_dec_sbox.setMinimum(-99.989999999999995)
        self.mag_dec_sbox.setSingleStep(0.500000000000000)

        self.verticalLayout.addWidget(self.mag_dec_sbox)

        self.line_3 = QFrame(self.frame)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.HLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.verticalLayout.addWidget(self.line_3)

        self.az_spline_cbox = QCheckBox(self.frame)
        self.az_spline_cbox.setObjectName(u"az_spline_cbox")
        self.az_spline_cbox.setEnabled(False)

        self.verticalLayout.addWidget(self.az_spline_cbox)

        self.dip_spline_cbox = QCheckBox(self.frame)
        self.dip_spline_cbox.setObjectName(u"dip_spline_cbox")
        self.dip_spline_cbox.setEnabled(False)

        self.verticalLayout.addWidget(self.dip_spline_cbox)

        self.line = QFrame(self.frame)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.verticalLayout.addWidget(self.line)

        self.show_tool_geom_cbox = QCheckBox(self.frame)
        self.show_tool_geom_cbox.setObjectName(u"show_tool_geom_cbox")
        self.show_tool_geom_cbox.setEnabled(False)
        self.show_tool_geom_cbox.setChecked(True)

        self.verticalLayout.addWidget(self.show_tool_geom_cbox)

        self.show_existing_geom_cbox = QCheckBox(self.frame)
        self.show_existing_geom_cbox.setObjectName(u"show_existing_geom_cbox")
        self.show_existing_geom_cbox.setEnabled(False)
        self.show_existing_geom_cbox.setChecked(True)

        self.verticalLayout.addWidget(self.show_existing_geom_cbox)

        self.show_imported_geom_cbox = QCheckBox(self.frame)
        self.show_imported_geom_cbox.setObjectName(u"show_imported_geom_cbox")
        self.show_imported_geom_cbox.setEnabled(False)
        self.show_imported_geom_cbox.setChecked(True)

        self.verticalLayout.addWidget(self.show_imported_geom_cbox)

        self.show_mag_cbox = QCheckBox(self.frame)
        self.show_mag_cbox.setObjectName(u"show_mag_cbox")
        self.show_mag_cbox.setEnabled(False)
        self.show_mag_cbox.setChecked(True)

        self.verticalLayout.addWidget(self.show_mag_cbox)

        self.line_2 = QFrame(self.frame)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.HLine)
        self.line_2.setFrameShadow(QFrame.Sunken)

        self.verticalLayout.addWidget(self.line_2)

        self.collar_az_cbox = QGroupBox(self.frame)
        self.collar_az_cbox.setObjectName(u"collar_az_cbox")
        self.collar_az_cbox.setFlat(False)
        self.collar_az_cbox.setCheckable(True)
        self.collar_az_cbox.setChecked(False)
        self.verticalLayout_3 = QVBoxLayout(self.collar_az_cbox)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.collar_az_sbox = QDoubleSpinBox(self.collar_az_cbox)
        self.collar_az_sbox.setObjectName(u"collar_az_sbox")
        self.collar_az_sbox.setMinimum(-360.000000000000000)
        self.collar_az_sbox.setMaximum(360.000000000000000)
        self.collar_az_sbox.setSingleStep(0.500000000000000)

        self.verticalLayout_3.addWidget(self.collar_az_sbox)


        self.verticalLayout.addWidget(self.collar_az_cbox)

        self.collar_dip_cbox = QGroupBox(self.frame)
        self.collar_dip_cbox.setObjectName(u"collar_dip_cbox")
        self.collar_dip_cbox.setFlat(False)
        self.collar_dip_cbox.setCheckable(True)
        self.collar_dip_cbox.setChecked(False)
        self.verticalLayout_4 = QVBoxLayout(self.collar_dip_cbox)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.collar_dip_sbox = QDoubleSpinBox(self.collar_dip_cbox)
        self.collar_dip_sbox.setObjectName(u"collar_dip_sbox")
        self.collar_dip_sbox.setMinimum(-90.000000000000000)
        self.collar_dip_sbox.setMaximum(90.000000000000000)
        self.collar_dip_sbox.setSingleStep(0.500000000000000)

        self.verticalLayout_4.addWidget(self.collar_dip_sbox)


        self.verticalLayout.addWidget(self.collar_dip_cbox)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy1)
        self.groupBox.setAlignment(Qt.AlignCenter)
        self.groupBox.setFlat(True)
        self.formLayout = QFormLayout(self.groupBox)
        self.formLayout.setObjectName(u"formLayout")
        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName(u"label_2")

        self.formLayout.setWidget(0, QFormLayout.SpanningRole, self.label_2)

        self.az_output_combo = QComboBox(self.groupBox)
        self.az_output_combo.setObjectName(u"az_output_combo")

        self.formLayout.setWidget(1, QFormLayout.SpanningRole, self.az_output_combo)

        self.label_3 = QLabel(self.groupBox)
        self.label_3.setObjectName(u"label_3")

        self.formLayout.setWidget(2, QFormLayout.SpanningRole, self.label_3)

        self.dip_output_combo = QComboBox(self.groupBox)
        self.dip_output_combo.setObjectName(u"dip_output_combo")

        self.formLayout.setWidget(3, QFormLayout.SpanningRole, self.dip_output_combo)

        self.cancel_btn = QPushButton(self.groupBox)
        self.cancel_btn.setObjectName(u"cancel_btn")

        self.formLayout.setWidget(5, QFormLayout.FieldRole, self.cancel_btn)

        self.accept_btn = QPushButton(self.groupBox)
        self.accept_btn.setObjectName(u"accept_btn")
        self.accept_btn.setEnabled(False)

        self.formLayout.setWidget(5, QFormLayout.LabelRole, self.accept_btn)

        self.verticalSpacer_2 = QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.formLayout.setItem(4, QFormLayout.LabelRole, self.verticalSpacer_2)


        self.verticalLayout.addWidget(self.groupBox)


        self.gridLayout.addWidget(self.frame, 0, 1, 1, 1)

        self.tabWidget_2 = QTabWidget(self.centralwidget)
        self.tabWidget_2.setObjectName(u"tabWidget_2")
        self.tabWidget_2Page1 = QWidget()
        self.tabWidget_2Page1.setObjectName(u"tabWidget_2Page1")
        self.verticalLayout_2 = QVBoxLayout(self.tabWidget_2Page1)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.plots_layout = QHBoxLayout()
        self.plots_layout.setObjectName(u"plots_layout")

        self.verticalLayout_2.addLayout(self.plots_layout)

        self.tabWidget_2.addTab(self.tabWidget_2Page1, "")
        self.tabWidget_2Page2 = QWidget()
        self.tabWidget_2Page2.setObjectName(u"tabWidget_2Page2")
        self.verticalLayout_6 = QVBoxLayout(self.tabWidget_2Page2)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.polar_plot_layout = QVBoxLayout()
        self.polar_plot_layout.setObjectName(u"polar_plot_layout")

        self.verticalLayout_6.addLayout(self.polar_plot_layout)

        self.tabWidget_2.addTab(self.tabWidget_2Page2, "")

        self.gridLayout.addWidget(self.tabWidget_2, 0, 2, 1, 1)

        PEMGeometry.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(PEMGeometry)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 943, 21))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuSettings = QMenu(self.menubar)
        self.menuSettings.setObjectName(u"menuSettings")
        PEMGeometry.setMenuBar(self.menubar)
        self.status_bar = QStatusBar(PEMGeometry)
        self.status_bar.setObjectName(u"status_bar")
        self.status_bar.setSizeGripEnabled(False)
        PEMGeometry.setStatusBar(self.status_bar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuSettings.menuAction())
        self.menuFile.addAction(self.actionOpen_Geometry_File)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionCopy_Screenshot)
        self.menuFile.addAction(self.actionSave_Screenshot)
        self.menuSettings.addAction(self.actionAllow_Negative_Azimuth)

        self.retranslateUi(PEMGeometry)

        self.tabWidget_2.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(PEMGeometry)
    # setupUi

    def retranslateUi(self, PEMGeometry):
        PEMGeometry.setWindowTitle(QCoreApplication.translate("PEMGeometry", u"MainWindow", None))
        self.actionOpen_Geometry_File.setText(QCoreApplication.translate("PEMGeometry", u"Open Geometry File", None))
        self.actionPolar_Plot.setText(QCoreApplication.translate("PEMGeometry", u"Polar Plot", None))
        self.actionAllow_Negative_Azimuth.setText(QCoreApplication.translate("PEMGeometry", u"Allow Negative Azimuth", None))
        self.actionCopy_Screenshot.setText(QCoreApplication.translate("PEMGeometry", u"Take Screenshot", None))
        self.actionSave_Screenshot.setText(QCoreApplication.translate("PEMGeometry", u"Save Screenshot", None))
        self.label.setText(QCoreApplication.translate("PEMGeometry", u"Magnetic Declination (\u00b0)", None))
        self.az_spline_cbox.setText(QCoreApplication.translate("PEMGeometry", u"Azimuth Spline", None))
        self.dip_spline_cbox.setText(QCoreApplication.translate("PEMGeometry", u"Dip Spline", None))
        self.show_tool_geom_cbox.setText(QCoreApplication.translate("PEMGeometry", u"Tool Geometry", None))
        self.show_existing_geom_cbox.setText(QCoreApplication.translate("PEMGeometry", u"Existing Geometry", None))
        self.show_imported_geom_cbox.setText(QCoreApplication.translate("PEMGeometry", u"Imported Geometry", None))
        self.show_mag_cbox.setText(QCoreApplication.translate("PEMGeometry", u"Magnetic Field Strength", None))
        self.collar_az_cbox.setTitle(QCoreApplication.translate("PEMGeometry", u"Fixed Azimuth", None))
        self.collar_dip_cbox.setTitle(QCoreApplication.translate("PEMGeometry", u"Fixed Dip", None))
        self.groupBox.setTitle(QCoreApplication.translate("PEMGeometry", u"Export", None))
        self.label_2.setText(QCoreApplication.translate("PEMGeometry", u"Azimuth", None))
        self.label_3.setText(QCoreApplication.translate("PEMGeometry", u"Dip", None))
        self.cancel_btn.setText(QCoreApplication.translate("PEMGeometry", u"Cancel", None))
        self.accept_btn.setText(QCoreApplication.translate("PEMGeometry", u"Accept", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tabWidget_2Page1), QCoreApplication.translate("PEMGeometry", u"Vertical Plots", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tabWidget_2Page2), QCoreApplication.translate("PEMGeometry", u"Polar Plot", None))
        self.menuFile.setTitle(QCoreApplication.translate("PEMGeometry", u"File", None))
        self.menuSettings.setTitle(QCoreApplication.translate("PEMGeometry", u"Settings", None))
    # retranslateUi

