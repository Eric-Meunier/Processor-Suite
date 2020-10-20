from PyQt5.QtWidgets import (QProgressBar)


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