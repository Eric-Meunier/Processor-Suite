# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'splash_screen.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_SplashScreen(object):
    def setupUi(self, SplashScreen):
        if not SplashScreen.objectName():
            SplashScreen.setObjectName(u"SplashScreen")
        SplashScreen.resize(545, 336)
        self.verticalLayout = QVBoxLayout(SplashScreen)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.frame = QFrame(SplashScreen)
        self.frame.setObjectName(u"frame")
        self.frame.setStyleSheet(u"QFrame{\n"
"	background-color:rgb(255, 255, 255);\n"
"	border-color:rgb(62, 255, 68);\n"
"	border-radius: 10px;\n"
"}")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.label = QLabel(self.frame)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(0, 60, 521, 71))
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        font = QFont()
        font.setFamily(u"Ebrima")
        font.setPointSize(44)
        font.setUnderline(False)
        font.setStrikeOut(False)
        font.setKerning(True)
        self.label.setFont(font)
        self.label.setStyleSheet(u"QLabel{color:rgb(27, 100, 56)}")
        self.label.setTextFormat(Qt.AutoText)
        self.label.setScaledContents(False)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMargin(0)
        self.label_2 = QLabel(self.frame)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(10, 60, 141, 91))
        self.label_2.setPixmap(QPixmap(u"icons/crone_logo.png"))
        self.label_2.setAlignment(Qt.AlignCenter)
        self.version_label = QLabel(self.frame)
        self.version_label.setObjectName(u"version_label")
        self.version_label.setGeometry(QRect(0, 130, 521, 21))
        font1 = QFont()
        font1.setFamily(u"Segoe UI")
        font1.setPointSize(12)
        self.version_label.setFont(font1)
        self.version_label.setStyleSheet(u"QLabel{color:rgb(27, 100, 56)}")
        self.version_label.setAlignment(Qt.AlignCenter)
        self.progressBar = QProgressBar(self.frame)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setGeometry(QRect(30, 240, 471, 23))
        self.progressBar.setStyleSheet(u"QProgressBar{\n"
"	text-align:center;\n"
"}\n"
"\n"
"QProgressBar::chunk{\n"
"	background-color:qlineargradient(spread:pad, x1:0, y1:0.477273, x2:0.988636, y2:0.477, stop:0 rgba(251, 195, 28, 255), stop:1 rgba(27, 100, 56, 255))\n"
"}")
        self.progressBar.setValue(24)
        self.message_label = QLabel(self.frame)
        self.message_label.setObjectName(u"message_label")
        self.message_label.setGeometry(QRect(36, 220, 461, 20))
        font2 = QFont()
        font2.setPointSize(7)
        self.message_label.setFont(font2)
        self.label.raise_()
        self.version_label.raise_()
        self.label_2.raise_()
        self.progressBar.raise_()
        self.message_label.raise_()

        self.verticalLayout.addWidget(self.frame)


        self.retranslateUi(SplashScreen)

        QMetaObject.connectSlotsByName(SplashScreen)
    # setupUi

    def retranslateUi(self, SplashScreen):
        SplashScreen.setWindowTitle(QCoreApplication.translate("SplashScreen", u"Form", None))
        self.label.setText(QCoreApplication.translate("SplashScreen", u"<strong><g>PEM</strong>Pro", None))
        self.label_2.setText("")
        self.version_label.setText(QCoreApplication.translate("SplashScreen", u"<html><head/><body><p>Version</p></body></html>", None))
        self.message_label.setText(QCoreApplication.translate("SplashScreen", u"Loading...", None))
    # retranslateUi

