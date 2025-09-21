# canDrive @ 2025
# To create a one-file executable, call: pyinstaller -F main.spec
#----------------------------------------------------------------
import serial
import canSniffer_ui
from PyQt5.QtWidgets import QMainWindow, QApplication, QTableWidgetItem, QHeaderView, QFileDialog, QRadioButton
from PyQt5.QtWidgets import QVBoxLayout, QCheckBox, QMessageBox, QTextEdit, QGroupBox, QPushButton, QToolTip, QLabel
from PyQt5.QtWidgets import QLineEdit, QHBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QCursor
import serial.tools.list_ports

import sys
import os
import time
from datetime import datetime
import qtmodern
from qtmodern import styles
from qtmodern import windows
import csv

import HideOldPackets
import SerialReader
import SerialWriter
import FileLoader

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True) #enable highdpi scaling
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True) #use highdpi icons

class canSnifferGUI(QMainWindow, canSniffer_ui.Ui_MainWindow):
    def __init__(self):
        super(canSnifferGUI, self).__init__()
        self.setupUi(self)

        # --- KWP2000 / ISO-TP (Flow Control only) ---
        self.kwpGroupBox = QGroupBox("KWP2000 / ISO-TP", self.centralwidget)
        self.kwpGroupBoxLayout = QVBoxLayout(self.kwpGroupBox)

        self.kwpEnableCheck = QCheckBox("Enable Flow Control (Send ACK on FF)")
        self.kwpEnableCheck.stateChanged.connect(self.onKwpToggle)
        self.kwpGroupBoxLayout.addWidget(self.kwpEnableCheck)

        idRow = QHBoxLayout()
        self.testerIdEdit = QLineEdit("7E0");
        self.testerIdEdit.setMaximumWidth(80)
        self.ecuIdEdit = QLineEdit("7E8");
        self.ecuIdEdit.setMaximumWidth(80)
        idRow.addWidget(QLabel("Tester ID (hex):"));
        idRow.addWidget(self.testerIdEdit)
        idRow.addSpacing(12)
        idRow.addWidget(QLabel("ECU ID (hex):"));
        idRow.addWidget(self.ecuIdEdit)
        self.kwpGroupBoxLayout.addLayout(idRow)

        self.applyIdsBtn = QPushButton("Apply IDs")
        self.applyIdsBtn.clicked.connect(self.onApplyIds)
        self.kwpGroupBoxLayout.addWidget(self.applyIdsBtn)

        self.verticalLayout_10.addWidget(self.kwpGroupBox)
        side_widget = self.verticalLayout_10.parentWidget()
        side_widget.setMinimumWidth(300)
        sp = side_widget.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Preferred)
        side_widget.setSizePolicy(sp)
        self.loadedFileLabel = QLabel("No file loaded", self)
        self.loadedFileLabel.setStyleSheet("color: #888;")  # diskret grå tekst
        self.loadedFileLabel.setTextInteractionFlags(Qt.TextSelectableByMouse)  # kan kopiere tekst
        parent_layout = self.loadSessionFromFileButton.parentWidget().layout()
        if parent_layout is not None:
            i = parent_layout.indexOf(self.loadSessionFromFileButton)
            parent_layout.insertWidget(i + 1, self.loadedFileLabel)

        self.tooltipUpdateTimer = QTimer()
        self.tooltipUpdateTimer.timeout.connect(self.updateHoveredTooltip)
        self.tooltipUpdateTimer.start(150)  # Oppdater hvert 150 ms

        self.espStatusLogBox = QTextEdit(self.centralwidget)
        self.espStatusLogBox.setReadOnly(True)
        self.espStatusLogBox.setStyleSheet("color: orange; background-color: #1e1e1e; font-family: Consolas;")
        self.espStatusLogBox.setLineWrapMode(QTextEdit.NoWrap)
        self.clearEspLogButton = QPushButton("Clear ESP Log")
        self.clearEspLogButton.clicked.connect(lambda: self.espStatusLogBox.clear())


        # Sett inn en gruppering med tittel, som ligner de andre panelene
        self.espGroupBox = QGroupBox("ESP32 status log", self.centralwidget)
        self.espGroupBoxLayout = QVBoxLayout(self.espGroupBox)
        self.espGroupBoxLayout.addWidget(self.espStatusLogBox)
        self.espGroupBoxLayout.addWidget(self.clearEspLogButton)

        # Legg denne til der du før brukte self.verticalLayout_10
        self.verticalLayout_10.addWidget(self.espGroupBox)

        self.mainMessageTableWidget.setMouseTracking(True)
        self.decodedMessagesTableWidget.setMouseTracking(True)
        self.txTable.setMouseTracking(True)
        self.mainMessageTableWidget.itemEntered.connect(self.showBitTooltip)
        self.decodedMessagesTableWidget.itemEntered.connect(self.showBitTooltip)
        self.txTable.itemEntered.connect(self.showBitTooltip)
        self.portScanButton.clicked.connect(self.scanPorts)
        self.portConnectButton.clicked.connect(self.serialPortConnect)
        self.portDisconnectButton.clicked.connect(self.serialPortDisconnect)
        self.startSniffingButton.clicked.connect(self.startSniffing)
        self.stopSniffingButton.clicked.connect(self.stopSniffing)
        self.saveSelectedIdInDictButton.clicked.connect(self.saveIdLabelToDictCallback)
        self.saveSessionToFileButton.clicked.connect(self.saveSessionToFile)
        self.loadSessionFromFileButton.clicked.connect(self.loadSessionFromFile)
        self.showOnlyIdsLineEdit.textChanged.connect(self.showOnlyIdsTextChanged)
        self.hideIdsLineEdit.textChanged.connect(self.hideIdsTextChanged)
        self.clearLabelDictButton.clicked.connect(self.clearLabelDict)
        self.serialController = serial.Serial()
        self.mainMessageTableWidget.cellClicked.connect(self.cellWasClicked)
        self.newTxTableRow.clicked.connect(self.newTxTableRowCallback)
        self.removeTxTableRow.clicked.connect(self.removeTxTableRowCallback)
        self.sendTxTableButton.clicked.connect(self.sendTxTableCallback)
        self.abortSessionLoadingButton.clicked.connect(self.abortSessionLoadingCallback)
        self.showSendingTableCheckBox.clicked.connect(self.showSendingTableButtonCallback)
        self.addToDecodedPushButton.clicked.connect(self.addToDecodedCallback)
        self.deleteDecodedPacketLinePushButton.clicked.connect(self.deleteDecodedLineCallback)
        self.deleteLabelLinePushButton.clicked.connect(self.deleteLabelLineCallback)
        self.decodedMessagesTableWidget.itemChanged.connect(self.decodedTableItemChangedCallback)
        self.clearTableButton.clicked.connect(self.clearTableCallback)
        self.sendSelectedDecodedPacketButton.clicked.connect(self.sendDecodedPacketCallback)
        self.playbackMainTableButton.clicked.connect(self.playbackMainTableCallback)
        self.stopPlayBackButton.clicked.connect(self.stopPlayBackCallback)
        self.hideAllPacketsButton.clicked.connect(self.hideAllPackets)
        self.showControlsButton.hide()

        self.serialWriterThread = SerialWriter.SerialWriterThread(self.serialController)
        self.serialReaderThread = SerialReader.SerialReaderThread(self.serialController)
        self.serialReaderThread.receivedPacketSignal.connect(self.handleSerialLine)
        self.fileLoaderThread = FileLoader.FileLoaderThread()
        self.fileLoaderThread.newRowSignal.connect(self.mainTablePopulatorCallback)
        self.fileLoaderThread.loadingFinishedSignal.connect(self.fileLoadingFinishedCallback)
        self.hideOldPacketsThread = HideOldPackets.HideOldPacketsThread()
        self.hideOldPacketsThread.hideOldPacketsSignal.connect(self.hideOldPacketsCallback)

        self.stopPlayBackButton.setVisible(False)
        self.playBackProgressBar.setVisible(False)
        self.sendingGroupBox.hide()
        self.hideOldPacketsThread.enable(5)
        self.hideOldPacketsThread.start()

        # If the timestamp of the exported decoded list is in millisec, it's compatible with SavvyCan's GVRET format.
        self.exportDecodedListInMillisecTimestamp = False

        self.scanPorts()
        self.startTime = 0
        self.receivedPackets = 0
        self.playbackMainTableIndex = 0
        self.labelDictFile = None
        self.idDict = dict([])
        self.showOnlyIdsSet = set([])
        self.hideIdsSet = set([])
        self.idLabelDict = dict()
        self.isInited = False
        self.init()

        if not os.path.exists("save"):
            os.makedirs("save")

        for i in range(6, self.mainMessageTableWidget.columnCount()):
            self.mainMessageTableWidget.setColumnWidth(i, 32)
        for i in range(6, self.mainMessageTableWidget.columnCount()):
            self.decodedMessagesTableWidget.setColumnWidth(i, 32)
        self.mainMessageTableWidget.setColumnWidth(2, 600)
        self.idLabelDictTable.setColumnWidth(1, 600)
        self.decodedMessagesTableWidget.setColumnWidth(1, 100)
        self.decodedMessagesTableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.txTable.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.txTable.setColumnWidth(1, 600)  # Kolonne 1 = ID Label i txTable
        self.txTable.setColumnWidth(3, 88)  # Kolonne 3 = Ext.ID i txTable
        #self.txTable.setColumnWidth(4, 600)  # Kolonne 4 = Data i txTable
        self.showMaximized()

    def onKwpToggle(self, state):
        """KWP/ISO-TP toggle → sender 'K1' (ON) eller 'K0' (OFF) til ESP."""
        try:
            ser = getattr(self.serialWriterThread, "serial", None)
            if not ser or not ser.is_open:
                QMessageBox.warning(self, "Serial", "Serial port not open.")
                return
            cmd = "K1\n" if state == Qt.Checked else "K0\n"
            ser.write(cmd.encode("ascii"))
        except Exception as e:
            QMessageBox.warning(self, "Serial", f"Failed to toggle KWP: {e}")

    def onApplyIds(self):
        """Sender IDT/IDE til ESP (hex uten 0x)."""
        try:
            ser = getattr(self.serialWriterThread, "serial", None)
            if not ser or not ser.is_open:
                QMessageBox.warning(self, "Serial", "Serial port not open.")
                return
            tid = int(self.testerIdEdit.text().strip(), 16)
            eid = int(self.ecuIdEdit.text().strip(), 16)
            # én linje som ESP-parsingen din forstår (eller behold IDT/IDE om du vil)
            ser.write(f"ID {tid:03X} {eid:03X}\n".encode("ascii"))
        except ValueError:
            QMessageBox.warning(self, "IDs", "Please enter valid hex IDs, e.g. 7E0 and 7E8.")
        except Exception as e:
            QMessageBox.warning(self, "Serial", f"Failed to apply IDs: {e}")

    def handleSerialLine(self, line):
        line = line.strip()
        if not line:
            return
        print("RECEIVED LINE:", line)

        if line.startswith("!"):
            # Status fra ESP32 (f.eks. !SEND OK)
            msg = line[1:].strip()
            print(f"ESP32 STATUS: {msg}")
            if hasattr(self, 'espStatusLogBox'):
                current_text = self.espStatusLogBox.toPlainText()
                self.espStatusLogBox.setPlainText(current_text + msg + "\n")
                self.espStatusLogBox.verticalScrollBar().setValue(self.espStatusLogBox.verticalScrollBar().maximum())
            return

        # Vanlig CAN-pakke
        timestamp = datetime.now().timestamp()
        self.serialPacketReceiverCallback(line, timestamp)

    def updateHoveredTooltip(self):
        widget = QApplication.widgetAt(QCursor.pos())
        if not isinstance(widget, QTableWidgetItem):
            # Vi må finne ut hvilket TableWidget og hvilken celle som er under musen
            for table in [self.mainMessageTableWidget, self.decodedMessagesTableWidget, self.txTable]:
                pos = table.viewport().mapFromGlobal(QCursor.pos())
                row = table.rowAt(pos.y())
                col = table.columnAt(pos.x())
                if row >= 0 and col >= 6 and col <= 13:  # D0–D7
                    item = table.item(row, col)
                    if item:
                        try:
                            byte = int(item.text(), 16)
                            tooltip = f"Byte: {item.text().strip().upper()}\nBits: {byte:08b}"
                        except:
                            tooltip = "Ugyldig hex-verdi"
                        item.setToolTip(tooltip)
                        QToolTip.showText(QCursor.pos(), tooltip)
                    return

    def showBitTooltip(self, item):
        column = item.column()
        if column >= 6 and column <= 13:  # D0 til D7
            value = item.text().strip()
            try:
                byte = int(value, 16)
                bitstring = format(byte, '08b')  # Binær med ledende nuller
                tooltip = f"Byte: {value.upper()}\nBits: {bitstring}"
            except ValueError:
                tooltip = "Ugyldig hex-verdi"
            item.setToolTip(tooltip)
        else:
            item.setToolTip("")

    def stopPlayBackCallback(self):
        try:
            self.serialWriterThread.packetSentSignal.disconnect()
        except:
            pass
        self.serialWriterThread.clearQueues()
        self.playbackMainTableButton.setVisible(True)
        self.stopPlayBackButton.setVisible(False)
        self.playBackProgressBar.setVisible(False)

    def setRadioButton(self, radioButton:QRadioButton, mode):
        radioButton.setAutoExclusive(False)
        if mode == 0:
            radioButton.setChecked(False)
        if mode == 1:
            radioButton.setChecked(True)
        if mode == 2:
            radioButton.setChecked(not radioButton.isChecked())
        radioButton.setAutoExclusive(True)
        QApplication.processEvents()

    def playbackMainTable1Packet(self):
        row = self.playbackMainTableIndex
        maxRows = self.mainMessageTableWidget.rowCount()

        if row >= maxRows:
            self.stopPlayBackCallback()
            return

        txBuf = ""
        id_item = self.mainMessageTableWidget.item(row, 1)
        id = id_item.text().split(" ")[0] if id_item and id_item.text() else ""
        if len(id) % 2:
            txBuf += '0'
        txBuf += id + ','

        rtr_item = self.mainMessageTableWidget.item(row, 3)
        ide_item = self.mainMessageTableWidget.item(row, 4)

        txBuf += (rtr_item.text() if rtr_item else "0") + ','
        txBuf += (ide_item.text() if ide_item else "0") + ','

        for i in range(6, self.mainMessageTableWidget.columnCount()):
            data_item = self.mainMessageTableWidget.item(row, i)
            txBuf += data_item.text() if data_item else ""

        txBuf += '\n'

        if row < maxRows - 1:
            try:
                t0 = float(self.mainMessageTableWidget.item(row, 0).text())
                t1 = float(self.mainMessageTableWidget.item(row + 1, 0).text())
                dt = abs(int((t0 - t1) * (1000 if '.' in str(t0) else 1)))
                self.serialWriterThread.setNormalWriteDelay(dt)
            except:
                self.serialWriterThread.setNormalWriteDelay(10)

        self.playBackProgressBar.setValue(int((row / maxRows) * 100))
        self.playbackMainTableIndex += 1

        id_item = self.mainMessageTableWidget.item(row, 1)
        rtr_item = self.mainMessageTableWidget.item(row, 3)
        ide_item = self.mainMessageTableWidget.item(row, 4)
        data_field = ""

        for i in range(6, self.mainMessageTableWidget.columnCount()):
            item = self.mainMessageTableWidget.item(row, i)
            if item and item.text().strip():
                data_field += item.text().strip()

        data_item = QTableWidgetItem(data_field)

        self.sendPacketToESP32(id_item, rtr_item, ide_item, data_item)

        if row < maxRows - 1:
            try:
                t0 = float(self.mainMessageTableWidget.item(row, 0).text())
                t1 = float(self.mainMessageTableWidget.item(row + 1, 0).text())
                dt = max(0, int(round((t1 - t0) * 1000)))  # ms mellom rad row og row+1
                self.serialWriterThread.setNormalWriteDelay(dt)
            except:
                self.serialWriterThread.setNormalWriteDelay(10)

    def playbackMainTableCallback(self):
        self.playbackMainTableButton.setVisible(False)
        self.stopPlayBackButton.setVisible(True)
        self.playBackProgressBar.setVisible(True)
        self.playbackMainTableIndex = 0
        self.serialWriterThread.setRepeatedWriteDelay(0)
        print('playing back...')
        self.serialWriterThread.packetSentSignal.connect(self.playbackMainTable1Packet)
        self.playbackMainTable1Packet()

    def clearTableCallback(self):
        self.idDict.clear()
        self.mainMessageTableWidget.setRowCount(0)

    def sendPacketToESP32(self, id_item, rtr_item, ide_item, data_item):
        if self.serialWriterThread.serial is None:
            QMessageBox.warning(self, "Serial Error", "Serial port not open.")
            return

        try:
            id_text = id_item.text().strip().lstrip("0x").upper()
            rtr = rtr_item.text().strip()
            ide = ide_item.text().strip()
            data_str = data_item.text().strip().replace(" ", "").upper()

            # ✅ Pad ID hvis nødvendig
            if len(id_text) % 2 != 0:
                id_text = "0" + id_text

            can_id = int(id_text, 16)

            # 🚀 Bygg meldingen
            message = f"{can_id:X},{rtr},{ide},{data_str}\n"
            print("SENDER:", message)

            self.serialWriterThread.serial.write(message.encode("ascii"))

        except Exception as e:
            print(f"Feil ved sending: {e}")
            QMessageBox.warning(self, "Send Error", str(e))

    def sendDecodedPacketCallback(self):
        self.newTxTableRowCallback()
        newRow = 0
        decodedCurrentRow = self.decodedMessagesTableWidget.currentRow()
        if decodedCurrentRow < 0:
            QMessageBox.warning(self, "No package selected", "You need to select a package to send.")
            return

        # ID fra kol 1 → TX kol 0
        newId = str(self.decodedMessagesTableWidget.item(decodedCurrentRow, 1).text()).split(" ")[0]
        self.txTable.setItem(newRow, 0, QTableWidgetItem(newId))

        # Label fra kol 2 → TX kol 1
        label = self.decodedMessagesTableWidget.item(decodedCurrentRow, 2)
        self.txTable.setItem(newRow, 1, QTableWidgetItem(label.text() if label else ""))

        # RTR fra kol 3 → TX kol 2
        rtr_item = self.decodedMessagesTableWidget.item(decodedCurrentRow, 3)
        self.txTable.setItem(newRow, 2, QTableWidgetItem(rtr_item.text() if rtr_item else ""))

        # IDE fra kol 4 → TX kol 3
        ide_item = self.decodedMessagesTableWidget.item(decodedCurrentRow, 4)
        self.txTable.setItem(newRow, 3, QTableWidgetItem(ide_item.text() if ide_item else ""))

        # DLC fra kol 5
        dlc_text = self.decodedMessagesTableWidget.item(decodedCurrentRow, 5).text()
        dlc = int(dlc_text, 16) if 'x' in dlc_text.lower() or len(dlc_text) > 2 else int(dlc_text)

        # D0–D7 fra kol 6+
        newData = ""
        for i in range(dlc):
            cell = self.decodedMessagesTableWidget.item(decodedCurrentRow, 6 + i)
            if cell:
                newData += cell.text()
        # Data → TX kol 4
        self.txTable.setItem(newRow, 4, QTableWidgetItem(newData))

        self.txTable.selectRow(newRow)

        #if self.sendTxTableButton.isEnabled():
        #    self.sendTxTableCallback()

    def decodedTableItemChangedCallback(self):
        if self.isInited:
            self.saveTableToFile(self.decodedMessagesTableWidget, "save/decodedPackets.csv")

    def deleteDecodedLineCallback(self):
        self.decodedMessagesTableWidget.removeRow(self.decodedMessagesTableWidget.currentRow())

    def deleteLabelLineCallback(self):
        self.idLabelDictTable.removeRow(self.idLabelDictTable.currentRow())

    def addToDecodedCallback(self):
        newRow = self.decodedMessagesTableWidget.rowCount()
        self.decodedMessagesTableWidget.insertRow(newRow)
        for i in range(1, self.decodedMessagesTableWidget.columnCount()):
            new_item = QTableWidgetItem(self.mainMessageTableWidget.item(self.mainMessageTableWidget.currentRow(), i))
            self.decodedMessagesTableWidget.setItem(newRow, i, new_item)

    def showSendingTableButtonCallback(self):
        if self.showSendingTableCheckBox.isChecked():
            self.sendingGroupBox.show()
        else:
            self.sendingGroupBox.hide()

    def hideAllPackets(self):
        text = ""
        for id in self.idDict:
            text += id + " "
        self.hideIdsLineEdit.setText(text)
        self.clearTableCallback()

    def hideOldPacketsCallback(self):
        if not self.hideOldPacketsCheckBox.isChecked():
            return
        if not self.groupModeCheckBox.isChecked():
            return
        for i in range(self.mainMessageTableWidget.rowCount()):
            if self.mainMessageTableWidget.isRowHidden(i):
                continue
            packetTime = float(self.mainMessageTableWidget.item(i, 0).text())
            if (time.time() - self.startTime) - packetTime > self.hideOldPeriod.value():
                # print("Hiding: " + str(self.mainMessageTableWidget.item(i,1).text()))
                # print(time.time() - self.start_time)
                self.mainMessageTableWidget.setRowHidden(i, True)

    def sendTxTableCallback(self):
        row = self.txTable.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No rows selected", "Select a row from table before sending.")
            return

        id_item = self.txTable.item(row, 0)
        rtr_item = self.txTable.item(row, 2)
        ide_item = self.txTable.item(row,3)
        data_item = self.txTable.item(row, 4)

        self.sendPacketToESP32(id_item, rtr_item, ide_item, data_item)

    def fileLoadingFinishedCallback(self):
        self.abortSessionLoadingButton.setEnabled(False)

    def abortSessionLoadingCallback(self):
        self.fileLoaderThread.stop()
        self.abortSessionLoadingButton.setEnabled(False)

    def removeTxTableRowCallback(self):
        try:
            self.txTable.removeRow(self.txTable.currentRow())
        except:
            print('cannot remove')

    def newTxTableRowCallback(self):
        newRow = 0
        self.txTable.insertRow(newRow)

    def showOnlyIdsTextChanged(self):
        self.showOnlyIdsSet.clear()
        self.showOnlyIdsSet = set(self.showOnlyIdsLineEdit.text().split(" "))

    def hideIdsTextChanged(self):
        self.hideIdsSet.clear()
        self.hideIdsSet = set(self.hideIdsLineEdit.text().split(" "))

    def init(self):
        self.loadTableFromFile(self.decodedMessagesTableWidget, "save/decodedPackets.csv")
        self.loadTableFromFile(self.idLabelDictTable, "save/labelDict.csv")
        for row in range(self.idLabelDictTable.rowCount()):
            self.idLabelDict[str(self.idLabelDictTable.item(row, 0).text())] = \
                item_key = self.idLabelDictTable.item(row, 0)
            item_val = self.idLabelDictTable.item(row, 1)

            if item_key is not None and item_val is not None:
                key = str(item_key.text()).strip()
                val = str(item_val.text()).strip()
                self.idLabelDict[key] = val
        self.isInited = True

    def clearLabelDict(self):
        self.idLabelDictTable.setRowCount(0)
        self.saveTableToFile(self.idLabelDictTable, "save/labelDict.csv")

    def saveTableToFile(self, table, path):
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, 'Save File', './save', 'CSV(*.csv)')
        if path != '':
            with open(str(path), 'w', newline='') as stream:
                writer = csv.writer(stream)
                for row in range(table.rowCount()-1, -1, -1):
                    rowData = []
                    for column in range(table.columnCount()):
                        item = table.item(row, column)
                        if item is not None:
                            tempItem = item.text()
                            if self.exportDecodedListInMillisecTimestamp and column == 0:
                                timeSplit = item.text().split('.')
                                sec = timeSplit[0]
                                ms = timeSplit[1][0:3]
                                tempItem = sec + ms
                            rowData.append(str(tempItem))
                        else:
                            rowData.append('')
                    writer.writerow(rowData)

    def mainTablePopulatorCallback(self, rowData):
        if self.showOnlyIdsCheckBox.isChecked():
            if str(rowData[1]) not in self.showOnlyIdsSet:
                return
        if self.hideIdsCheckBox.isChecked():
            if str(rowData[1]) in self.hideIdsSet:
                return

        newId = str(rowData[1])
        row = 0

        if self.groupModeCheckBox.isChecked():
            if newId in self.idDict:
                row = self.idDict[newId]
            else:
                row = self.mainMessageTableWidget.rowCount()
                self.mainMessageTableWidget.insertRow(row)
        else:
            row = self.mainMessageTableWidget.rowCount()
            self.mainMessageTableWidget.insertRow(row)

        if self.mainMessageTableWidget.isRowHidden(row):
            self.mainMessageTableWidget.setRowHidden(row, False)

        # Sett ID (kol 1) og Label (kol 2)
        self.mainMessageTableWidget.setItem(row, 1, QTableWidgetItem(newId))
        label = self.idLabelDict.get(newId, "")
        labelItem = QTableWidgetItem(label)
        labelItem.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.mainMessageTableWidget.setItem(row, 2, labelItem)

        # Sett resten av data, forskjøvet én kolonne pga. Label
        for i in range(len(rowData)):
            table_col = i if i < 2 else i + 1  # hopp over kol 2
            if i >= 5:  # kolonner etter DLC → D0–D7
                try:
                    byte = int(rowData[i], 16)
                    text = f"{byte:02X}"
                except ValueError:
                    text = rowData[i]
            else:
                text = str(rowData[i])

            item = self.mainMessageTableWidget.item(row, table_col)
            if item is None:
                item = QTableWidgetItem()
                self.mainMessageTableWidget.setItem(row, table_col, item)

            #item.setText(text)

            # Highlight ny data
            # Bare oppdater hvis teksten faktisk er endret
            existing_text = item.text()
            if existing_text != text:
                item.setText(text)
                if self.highlightNewDataCheckBox.isChecked() and self.groupModeCheckBox.isChecked() and table_col > 4:
                    item.setBackground(QColor(245, 110, 234))
            else:
                # Hvis ikke data har endret seg, fjern eventuell gammel highlight
                item.setBackground(QColor(255, 255, 255))  # resetter til standard

        # Highlight ny ID
        if self.highlightNewIdCheckBox.isChecked() and newId not in self.idDict:
            for j in range(3):
                self.mainMessageTableWidget.item(row, j).setBackground(QColor(132, 119, 245))

        self.idDict[newId] = row

        # Farge hele raden grønnaktig hvis kjent ID
        if label:
            for i in range(self.mainMessageTableWidget.columnCount()):
                if i < 3:
                    self.mainMessageTableWidget.item(row, i).setBackground(QColor(139, 240, 136))

        # Juster all tekst
        for i in range(self.mainMessageTableWidget.columnCount()):
            item = self.mainMessageTableWidget.item(row, i)
            if item:
                align = Qt.AlignVCenter | (Qt.AlignLeft if i == 2 else Qt.AlignHCenter)
                item.setTextAlignment(align)

        # Oppdater teller
        self.receivedPackets += 1
        self.packageCounterLabel.setText(str(self.receivedPackets))

    def loadTableFromFile(self, table, path):
        if table == self.mainMessageTableWidget:
            if path is None:
                path, _ = QFileDialog.getOpenFileName(self, 'Open File', './save', 'CSV(*.csv)')
            if path:
                # Vis valgt filnavn under knappen
                try:
                    fn = os.path.basename(path)
                    self.loadedFileLabel.setText(fn)
                    self.loadedFileLabel.setToolTip(path)  # full sti som tooltip
                except Exception:
                    self.loadedFileLabel.setText("No file loaded")

                self.fileLoaderThread.enable(path, self.playbackDelaySpinBox.value())
                self.fileLoaderThread.start()
                self.abortSessionLoadingButton.setEnabled(True)
                return True
            else:
                # Hvis bruker kansellerer, vis "No file loaded"
                self.loadedFileLabel.setText("No file loaded")
                return False
        else:
            if path is None:
                path, _ = QFileDialog.getOpenFileName(self, 'Open File', './save', 'CSV(*.csv)')
            if path:
                try:
                    with open(path, 'r', newline='') as stream:
                        reader = csv.reader(stream)
                        for rowData in reader:
                            if not rowData or all(cell.strip() == "" for cell in rowData):
                                continue
                            if rowData[0].strip().lower() in ["timestamp", "time"]:
                                continue
                            while len(rowData) < table.columnCount():
                                rowData.append("")
                            row = table.rowCount()
                            table.insertRow(row)
                            for column in range(table.columnCount()):
                                item = QTableWidgetItem(rowData[column])
                                table.setItem(row, column, item)
                except OSError:
                    print("File not found:", path)

    def loadSessionFromFile(self):
        if self.autoclearCheckBox.isChecked():
            self.idDict.clear()
            self.mainMessageTableWidget.setRowCount(0)
        self.loadTableFromFile(self.mainMessageTableWidget, None)

    def saveSessionToFile(self):
        self.saveTableToFile(self.mainMessageTableWidget, None)

    def cellWasClicked(self):
        self.saveIdToDictLineEdit.setText(self.mainMessageTableWidget.item(self.mainMessageTableWidget.currentRow(), 1).text())

    def saveIdLabelToDictCallback(self):
        if (not self.saveIdToDictLineEdit.text()) or (not self.saveLabelToDictLineEdit.text()):
            return

        newRow = self.idLabelDictTable.rowCount()
        self.idLabelDictTable.insertRow(newRow)

        # ID (kolonne 0)
        idItem = QTableWidgetItem(self.saveIdToDictLineEdit.text())
        idItem.setTextAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        self.idLabelDictTable.setItem(newRow, 0, idItem)

        # Label (kolonne 1)
        labelItem = QTableWidgetItem(self.saveLabelToDictLineEdit.text())
        labelItem.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.idLabelDictTable.setItem(newRow, 1, labelItem)

        # Oppdater interne dict og lagre
        self.idLabelDict[str(self.saveIdToDictLineEdit.text())] = str(self.saveLabelToDictLineEdit.text())
        self.saveIdToDictLineEdit.setText('')
        self.saveLabelToDictLineEdit.setText('')
        self.saveTableToFile(self.idLabelDictTable, "save/labelDict.csv")

    def startSniffing(self):
        if self.autoclearCheckBox.isChecked():
            self.idDict.clear()
            self.mainMessageTableWidget.setRowCount(0)
        self.startSniffingButton.setEnabled(False)
        self.stopSniffingButton.setEnabled(True)
        self.sendTxTableButton.setEnabled(True)
        self.activeChannelComboBox.setEnabled(False)

        if self.activeChannelComboBox.isEnabled():
            txBuf = [0x42, self.activeChannelComboBox.currentIndex()]   # TX FORWARDER
            id_item = self.txTable.item(row, 0)
            rtr_item = self.txTable.item(row, 1)
            ide_item = self.txTable.item(row, 2)
            data_item = self.txTable.item(row, 4)

            self.sendPacketToESP32(id_item, rtr_item, ide_item, data_item)

            txBuf = [0x41, 1 << self.activeChannelComboBox.currentIndex()]  # RX FORWARDER
            id_item = self.txTable.item(row, 0)
            rtr_item = self.txTable.item(row, 1)
            ide_item = self.txTable.item(row, 2)
            data_item = self.txTable.item(row, 4)

            self.sendPacketToESP32(id_item, rtr_item, ide_item, data_item)

        self.startTime = time.time()

    def stopSniffing(self):
        self.startSniffingButton.setEnabled(True)
        self.stopSniffingButton.setEnabled(False)
        self.sendTxTableButton.setEnabled(False)
        self.activeChannelComboBox.setEnabled(True)
        self.setRadioButton(self.rxDataRadioButton, 0)

    def serialPacketReceiverCallback(self, packet, time):
        if self.startSniffingButton.isEnabled():
            return

        packet = packet.strip()
        print("RECEIVED LINE:", packet)
        packetSplit = packet.split(',')

        if len(packetSplit) != 4:
            print("wrong packet!" + packet)
            self.snifferMsgPlainTextEdit.document().setPlainText(packet)
            return

        rowData = [str(time - self.startTime)[:7]]  # timestamp
        rowData += packetSplit[0:3]  # ID, RTR, IDE

        datafield = packetSplit[3].strip()
        # 🔧 Fikser byte-padding
        if len(datafield) % 2 != 0:
            datafield = "0" + datafield

        DLC = len(datafield) // 2
        rowData.append(f"{DLC:02X}")

        if DLC > 0:
            rowData += [datafield[i:i + 2].upper() for i in range(0, len(datafield), 2)]

        self.mainTablePopulatorCallback(rowData)

    def serialPortConnect(self):
        try:
            self.serialController.port = self.portSelectorComboBox.currentText()
            self.serialController.baudrate = 250000
            self.serialController.open()
            self.espStatusLogBox.clear() # Clear ESP32 Log when doing new connection
            self.serialReaderThread.start()
            self.serialWriterThread.start()
            self.serialConnectedCheckBox.setChecked(True)
            self.portDisconnectButton.setEnabled(True)
            self.portConnectButton.setEnabled(False)
            self.startSniffingButton.setEnabled(True)
            self.stopSniffingButton.setEnabled(False)
            self.playbackMainTableButton.setEnabled(True)  # Aktiver playback-knapp ved oppstart
        except serial.SerialException as e:
            print('Error opening port: ' + str(e))

    def serialPortDisconnect(self):
        if self.stopSniffingButton.isEnabled():
            self.stopSniffing()
        try:
            self.serialReaderThread.stop()
            self.serialWriterThread.stop()
            self.portDisconnectButton.setEnabled(False)
            self.portConnectButton.setEnabled(True)
            self.startSniffingButton.setEnabled(False)
            self.serialConnectedCheckBox.setChecked(False)
            self.serialController.close()
            self.playbackMainTableButton.setEnabled(False)  # Deaktiver playback-knapp ved oppstart
        except serial.SerialException as e:
            print('Error closing port: ' + str(e))

    def scanPorts(self):
        self.portSelectorComboBox.clear()
        comPorts = serial.tools.list_ports.comports()
        nameList = list(port.device for port in comPorts)
        for name in nameList:
            self.portSelectorComboBox.addItem(name)


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)

def main():
    # excepthook redirect
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    # creating app
    app = QApplication(sys.argv)
    gui = canSnifferGUI()

    #applying dark theme
    #qtmodern.styles.dark(app)
    #darked_gui = qtmodern.windows.ModernWindow(gui)

    # adding a grip to the top left corner to make the frameless window resizable
    #layout = QVBoxLayout()
    #sizegrip = QSizeGrip(darked_gui)
    #sizegrip.setMaximumSize(30, 30)
    #layout.addWidget(sizegrip, 50, Qt.AlignBottom | Qt.AlignRight)
    #darked_gui.setLayout(layout)

    #starting the app
    gui.show()
    app.exec_()


if __name__ == "__main__":
    main()
