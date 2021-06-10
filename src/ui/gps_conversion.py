# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'gps_conversion.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_GPSConversion(object):
    def setupUi(self, GPSConversion):
        if not GPSConversion.objectName():
            GPSConversion.setObjectName(u"GPSConversion")
        GPSConversion.resize(286, 201)
        icon = QIcon()
        icon.addFile(u"icons/convert_gps.png", QSize(), QIcon.Normal, QIcon.Off)
        GPSConversion.setWindowIcon(icon)
        self.gridLayout = QGridLayout(GPSConversion)
        self.gridLayout.setObjectName(u"gridLayout")
        self.button_box = QDialogButtonBox(GPSConversion)
        self.button_box.setObjectName(u"button_box")
        self.button_box.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.button_box.setCenterButtons(True)

        self.gridLayout.addWidget(self.button_box, 3, 0, 1, 2)

        self.current_crs_label = QLabel(GPSConversion)
        self.current_crs_label.setObjectName(u"current_crs_label")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.current_crs_label.sizePolicy().hasHeightForWidth())
        self.current_crs_label.setSizePolicy(sizePolicy)

        self.gridLayout.addWidget(self.current_crs_label, 0, 1, 1, 1)

        self.label = QLabel(GPSConversion)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.label_3 = QLabel(GPSConversion)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 1)

        self.frame = QFrame(GPSConversion)
        self.frame.setObjectName(u"frame")
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.gridLayout_2 = QGridLayout(self.frame)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.epsg_rbtn = QRadioButton(self.frame)
        self.epsg_rbtn.setObjectName(u"epsg_rbtn")

        self.gridLayout_2.addWidget(self.epsg_rbtn, 4, 0, 1, 1)

        self.gps_zone_cbox = QComboBox(self.frame)
        self.gps_zone_cbox.setObjectName(u"gps_zone_cbox")
        self.gps_zone_cbox.setEnabled(False)

        self.gridLayout_2.addWidget(self.gps_zone_cbox, 1, 2, 1, 1)

        self.epsg_edit = QLineEdit(self.frame)
        self.epsg_edit.setObjectName(u"epsg_edit")
        self.epsg_edit.setEnabled(False)

        self.gridLayout_2.addWidget(self.epsg_edit, 4, 2, 1, 1)

        self.crs_rbtn = QRadioButton(self.frame)
        self.crs_rbtn.setObjectName(u"crs_rbtn")
        self.crs_rbtn.setChecked(True)

        self.gridLayout_2.addWidget(self.crs_rbtn, 1, 0, 1, 1)

        self.gps_system_cbox = QComboBox(self.frame)
        self.gps_system_cbox.setObjectName(u"gps_system_cbox")

        self.gridLayout_2.addWidget(self.gps_system_cbox, 0, 2, 1, 1)

        self.gps_datum_cbox = QComboBox(self.frame)
        self.gps_datum_cbox.setObjectName(u"gps_datum_cbox")
        self.gps_datum_cbox.setEnabled(False)

        self.gridLayout_2.addWidget(self.gps_datum_cbox, 2, 2, 1, 1)

        self.label_2 = QLabel(self.frame)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_2.addWidget(self.label_2, 4, 1, 1, 1)

        self.label_4 = QLabel(self.frame)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_2.addWidget(self.label_4, 0, 1, 1, 1)

        self.label_5 = QLabel(self.frame)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_2.addWidget(self.label_5, 1, 1, 1, 1)

        self.label_6 = QLabel(self.frame)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_2.addWidget(self.label_6, 2, 1, 1, 1)


        self.gridLayout.addWidget(self.frame, 2, 0, 1, 2)

        self.convert_to_label = QLabel(GPSConversion)
        self.convert_to_label.setObjectName(u"convert_to_label")

        self.gridLayout.addWidget(self.convert_to_label, 1, 1, 1, 1)


        self.retranslateUi(GPSConversion)

        QMetaObject.connectSlotsByName(GPSConversion)
    # setupUi

    def retranslateUi(self, GPSConversion):
        GPSConversion.setWindowTitle(QCoreApplication.translate("GPSConversion", u"GPS Conversion", None))
        self.current_crs_label.setText(QCoreApplication.translate("GPSConversion", u"TextLabel", None))
        self.label.setText(QCoreApplication.translate("GPSConversion", u"Current CRS:", None))
        self.label_3.setText(QCoreApplication.translate("GPSConversion", u"Convert to:", None))
        self.epsg_rbtn.setText("")
        self.crs_rbtn.setText("")
        self.label_2.setText(QCoreApplication.translate("GPSConversion", u"EPSG:", None))
        self.label_4.setText(QCoreApplication.translate("GPSConversion", u"System:", None))
        self.label_5.setText(QCoreApplication.translate("GPSConversion", u"Zone:", None))
        self.label_6.setText(QCoreApplication.translate("GPSConversion", u"Datum:", None))
        self.convert_to_label.setText(QCoreApplication.translate("GPSConversion", u"TextLabel", None))
    # retranslateUi

