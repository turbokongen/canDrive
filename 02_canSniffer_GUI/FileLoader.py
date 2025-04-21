import csv
from PyQt5 import QtCore

class FileLoaderThread(QtCore.QThread):
    newRowSignal = QtCore.pyqtSignal(list)
    loadingFinishedSignal = QtCore.pyqtSignal()

    def __init__(self):
        super(FileLoaderThread, self).__init__()
        self.path = None
        self.delayMs = 0
        self.isRunning = False

    def enable(self, path, delayMs):
        self.path = path
        self.delayMs = delayMs
        self.isRunning = True

    def stop(self):
        self.isRunning = False

    def run(self):
        while self.isRunning:
            if self.path is not None:
                try:
                    with open(str(self.path), 'r') as stream:
                        rows = list(csv.reader(stream))
                        for rowData in reversed(rows):
                            if not self.isRunning:
                                break
                            if not rowData or len(rowData) < 6:
                                continue  # hopp over ufullstendige rader

                            timestamp = rowData[0]
                            can_id = rowData[1]

                            # 🔧 Forskjøvet parsing basert på antall kolonner
                            if len(rowData) >= 14:
                                rtr = rowData[3]
                                ide = rowData[4]
                                dlc = rowData[5]
                                data = rowData[6:]
                            else:
                                rtr = rowData[2]
                                ide = rowData[3]
                                dlc = rowData[4]
                                data = rowData[5:]

                            while len(data) < 8:
                                data.append("")

                            gui_row = [timestamp, can_id, rtr, ide, dlc] + data[:8]
                            self.newRowSignal.emit(gui_row)

                            self.msleep(self.delayMs)

                    self.loadingFinishedSignal.emit()

                except OSError:
                    print("file not found: " + self.path)
                self.stop()
