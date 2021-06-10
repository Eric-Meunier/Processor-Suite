# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'line_name_editor.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_LineNameEditor(object):
    def setupUi(self, LineNameEditor):
        if not LineNameEditor.objectName():
            LineNameEditor.setObjectName(u"LineNameEditor")
        LineNameEditor.resize(320, 302)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(LineNameEditor.sizePolicy().hasHeightForWidth())
        LineNameEditor.setSizePolicy(sizePolicy)
        LineNameEditor.setMinimumSize(QSize(0, 0))
        self.formLayout = QFormLayout(LineNameEditor)
        self.formLayout.setObjectName(u"formLayout")
        self.label = QLabel(LineNameEditor)
        self.label.setObjectName(u"label")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.label)

        self.removeEdit = QLineEdit(LineNameEditor)
        self.removeEdit.setObjectName(u"removeEdit")

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.removeEdit)

        self.label_2 = QLabel(LineNameEditor)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.label_2)

        self.addEdit = QLineEdit(LineNameEditor)
        self.addEdit.setObjectName(u"addEdit")

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.addEdit)

        self.table = QTableWidget(LineNameEditor)
        self.table.setObjectName(u"table")
        self.table.setMinimumSize(QSize(0, 200))
        font = QFont()
        font.setFamily(u"Century Gothic")
        self.table.setFont(font)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setVisible(True)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setHighlightSections(False)

        self.formLayout.setWidget(2, QFormLayout.SpanningRole, self.table)

        self.buttonBox = QDialogButtonBox(LineNameEditor)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Close|QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(True)

        self.formLayout.setWidget(3, QFormLayout.SpanningRole, self.buttonBox)


        self.retranslateUi(LineNameEditor)

        QMetaObject.connectSlotsByName(LineNameEditor)
    # setupUi

    def retranslateUi(self, LineNameEditor):
        LineNameEditor.setWindowTitle(QCoreApplication.translate("LineNameEditor", u"Form", None))
        self.label.setText(QCoreApplication.translate("LineNameEditor", u"Remove:", None))
        self.label_2.setText(QCoreApplication.translate("LineNameEditor", u"Add:", None))
        self.addEdit.setInputMask("")
        self.addEdit.setPlaceholderText("")
    # retranslateUi

