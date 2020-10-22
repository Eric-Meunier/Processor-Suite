from PyQt5.QtWidgets import (QProgressBar)
import pyqtgraph as pg


class CustomProgressBar(QProgressBar):

    def __init__(self):
        super().__init__()
        # self.setFixedHeight(40)
        # self.setFixedWidth(120)

        COMPLETED_STYLE = """
        QProgressBar {
            border: 2px solid grey;
            border-radius: 5px;
            text-align: center;
        }

        QProgressBar::chunk {
            background-color: #88B0EB;
            width: 20px;
        }
        """
        # '#37DA7E' for green
        self.setStyleSheet(COMPLETED_STYLE)


class NonScientific(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super(NonScientific, self).__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        return [int(value*1) for value in values]  # This line return the NonScientific notation value

    def logTickStrings(self, values, scale, spacing):
        return [int(value*1) for value in values]  # This line return the NonScientific notation value
