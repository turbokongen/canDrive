from PyQt5 import QtWidgets

class BitViewer(QtWidgets.QGroupBox):
    def __init__(self):
        super().__init__("Bit View")
        self.setLayout(QtWidgets.QVBoxLayout())
        self.bitLabels = []
        for i in range(8):
            label = QtWidgets.QLabel(f"D{i}: --------")
            label.setFont(QtWidgets.QFont("Courier", 10))
            self.layout().addWidget(label)
            self.bitLabels.append(label)

    def updateBits(self, byte_values):
        for i, val in enumerate(byte_values):
            if i < len(self.bitLabels):
                try:
                    int_val = int(val, 16)
                    self.bitLabels[i].setText(f"D{i}: {int_val:08b}")
                except ValueError:
                    self.bitLabels[i].setText(f"D{i}: --------")