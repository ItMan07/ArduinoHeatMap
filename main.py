import datetime
import sys
import time

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QIODevice, Qt
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QMessageBox, QWidget, \
    QPushButton, QComboBox, QLabel, QTextEdit, QHBoxLayout, QLineEdit, QSplitter


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ===========================================================
        # НЕ ЗАБУДЬ УСТАНОВИТЬ СКОРОСТЬ ПОРТА
        self.baudRate = 9600

        # динамичный - 1, статичный - 0
        self.heatmap_mode = 0
        self.min_heatmap_value = 0.0
        self.max_heatmap_value = 100.0

        # ===========================================================

        self.setWindowTitle("Arduino")
        self.setGeometry(100, 100, 1000, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.port_layout = QHBoxLayout()
        self.layout.addLayout(self.port_layout)

        # =====

        self.port_label = QLabel("Выберите порт:", self)
        self.port_layout.addWidget(self.port_label)

        self.port_combo_box = QComboBox(self)
        self.port_layout.addWidget(self.port_combo_box)

        self.refresh_button = QPushButton("Обновить порты", self)
        self.port_layout.addWidget(self.refresh_button)
        self.refresh_button.clicked.connect(self.refresh_ports)

        self.connect_button = QPushButton("Подключиться", self)
        self.port_layout.addWidget(self.connect_button)
        self.connect_button.clicked.connect(self.connect_button_clicked)

        self.disconnect_button = QPushButton("Отключиться", self)
        self.port_layout.addWidget(self.disconnect_button)
        self.disconnect_button.clicked.connect(self.disconnect_button_clicked)

        self.stop_button = QPushButton("Остановить", self)
        self.port_layout.addWidget(self.stop_button)
        self.stop_button.clicked.connect(self.stop_getting_data)

        # =====

        self.data_layout = QHBoxLayout()
        self.layout.addLayout(self.data_layout)

        self.x_label = QLabel("X:", self)
        self.data_layout.addWidget(self.x_label)
        self.x_input = QLineEdit(self)
        self.data_layout.addWidget(self.x_input)

        self.y_label = QLabel("Y:", self)
        self.data_layout.addWidget(self.y_label)
        self.y_input = QLineEdit(self)
        self.data_layout.addWidget(self.y_input)

        self.send_button = QPushButton("Отправить", self)
        self.data_layout.addWidget(self.send_button)
        self.send_button.clicked.connect(self.send_data)

        self.sleep_time_label = QLabel("Время ожидания после получения пакета данных (мс):", self)
        self.data_layout.addWidget(self.sleep_time_label)
        self.sleep_time_input = QLineEdit(self)
        self.data_layout.addWidget(self.sleep_time_input)

        self.confirm_sleep_time_button = QPushButton("Установить", self)
        self.data_layout.addWidget(self.confirm_sleep_time_button)
        self.confirm_sleep_time_button.clicked.connect(self.confirm_sleep_time)

        # =====

        self.splitter = QSplitter(self)
        self.splitter.setOrientation(Qt.Horizontal)  # Горизонтальное разделение

        self.log_text_edit = QTextEdit(self)
        self.splitter.addWidget(self.log_text_edit)

        pg.setConfigOption('background', 'white')
        self.graphWidget = pg.ImageView()

        colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]
        cmap = pg.ColorMap(pos=np.linspace(0.0, 1.0, 3), color=colors)

        self.graphWidget.setColorMap(cmap)
        self.graphWidget.setImage(
            np.array([
                [3, 1, 3],
                [1, 3, 1],
                [3, 1, 3]
            ]).T
        )

        self.splitter.addWidget(self.graphWidget)
        self.layout.addWidget(self.splitter)

        # =====

        self.footer_layout = QHBoxLayout()
        self.layout.addLayout(self.footer_layout)

        self.clear_log_button = QPushButton("Очистить лог", self)
        self.footer_layout.addWidget(self.clear_log_button)
        self.clear_log_button.clicked.connect(self.clear_log)

        self.clear_heatmap_button = QPushButton("Очистить тепловую карту", self)
        self.footer_layout.addWidget(self.clear_heatmap_button)
        self.clear_heatmap_button.clicked.connect(self.clear_heatmap)

        # =====

        self.serial = None
        self.stop = False

        self.x = -1
        self.y = -1
        self.sleep_time = -1

        self.stop_timer = 0
        self.read_line_cnt = 0

        self.heatmap_data = []

    def send_data(self):
        if self.serial and self.serial.isOpen():
            if self.x_input.text() and self.y_input.text():
                self.x = int(self.x_input.text())
                self.y = int(self.y_input.text())
                data = f"{self.x},{self.y};"
                self.serial.write(data.encode())
                self.x_input.clear()
                self.y_input.clear()
                self.log_text_edit.append(f"[DATA] Отправлены данные (X:{self.x} Y:{self.y})\n")

    def refresh_ports(self):
        """
        Перезагрузка доступных COM портов
        """
        self.port_combo_box.clear()
        ports = QSerialPortInfo.availablePorts()
        for port in ports:
            self.port_combo_box.addItem(port.portName())
        self.log_text_edit.append(f"[INFO] Перезагрузка доступных COM портов\n")

    def connect_button_clicked(self):
        """
        Подключение к COM порту при нажатии кнопки
        """
        port_name = self.port_combo_box.currentText()
        QMessageBox.critical(self, "Ошибка скорости порта", "Установите правильную скорость порта") \
            if self.baudRate == 0 or type(self.baudRate) != int else 0
        if port_name:
            try:
                self.serial = QSerialPort()
                self.serial.setPortName(port_name)
                self.serial.setBaudRate(self.baudRate)
                self.serial.readyRead.connect(self.read_from_serial)

                self.serial.clear()
                self.read_line_cnt = 0

                if self.serial.open(QIODevice.ReadWrite):
                    self.connect_button.setEnabled(False)
                    self.disconnect_button.setEnabled(True)
                    self.refresh_button.setEnabled(False)
                    self.port_combo_box.setEnabled(False)
                    self.port_label.setText(f"Подключен к порту: {port_name}")
                    self.log_text_edit.append(f"[INFO] Подключен к порту: {port_name}\n")
                    self.log_text_edit.append(f"[INFO] Настройте координаты (X, Y) и время ожидания\n")
                    self.read_from_serial()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к порту")
                    self.log_text_edit.append(f"[ERROR] Не удалось подключиться к порту\n")
            except:
                QMessageBox.critical(self, "Ошибка", "Ошибка подключения к COM порту")
                self.log_text_edit.append(f"[ERROR] Ошибка подключения к COM порту\n")
        else:
            QMessageBox.warning(self, "Предупреждение", "Выберите порт для подключения")
            self.log_text_edit.append(f"[ERROR] Выберите порт для подключения\n")

    def disconnect_button_clicked(self):
        """
        Отключение от COM порта при нажатии кнопки
        """
        if self.serial is not None and self.serial.isOpen():
            self.serial.clear()
            self.read_line_cnt = 0

            self.serial.close()
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.refresh_button.setEnabled(True)
            self.port_combo_box.setEnabled(True)
            self.port_label.setText("Выберите порт:")
            self.log_text_edit.append(f"[INFO] Отключено\n")

    def read_from_serial(self):
        """
        Чтение данных из порта
        """
        if self.serial and self.serial.isOpen():
            if self.serial.canReadLine():
                data = self.serial.readLine()
                if self.stop is False:
                    if (self.x > 0) and (self.y > 0) and (self.sleep_time > 0) and (
                            time.time() - self.stop_timer >= (self.sleep_time / 1000)
                    ):
                        if self.read_line_cnt <= self.y:
                            self.read_line_cnt += 1
                            if data:
                                data = data.data().decode('utf-8', errors='ignore').strip()

                                data_int = list(map(int, data.split()))
                                self.heatmap_data.append(data_int)
                                self.process_data(f"[{self.read_line_cnt}] " + data)

                        if self.read_line_cnt == self.y:
                            self.show_data_on_heatmap(self.heatmap_data)
                            self.read_line_cnt = 0
                            self.heatmap_data = []

                            self.log_text_edit.append(f"[INFO] Ожидание {self.sleep_time} мс\n")
                            self.stop_timer = time.time()
                            self.serial.clear()

    def process_data(self, data):
        """
        Обработка поступивших данных и вывод
        """
        text = f'{datetime.datetime.now()}: {data}\n'
        self.log_text_edit.append(text)
        with open('data.txt', 'a') as file:
            file.write(text + '\n')

    def show_data_on_heatmap(self, new_data):
        try:
            new_data = np.array(new_data).T
            self.graphWidget.setImage(new_data)
            if not self.heatmap_mode:
                self.graphWidget.setLevels(self.min_heatmap_value, self.max_heatmap_value)
        except:
            self.log_text_edit.append(f"[ERROR] Произошла ошибка с получением данных. Перезагрузите программу. "
                                      f"Полученные данные с Ардуино будут сброшены\n")
            self.heatmap_data = []

    def clear_log(self):
        """
        Очистка лога
        """
        self.log_text_edit.clear()

    def clear_heatmap(self):
        self.graphWidget.setImage(
            np.array([
                [3, 1, 3],
                [1, 3, 1],
                [3, 1, 3]
            ]).T
        )
        self.log_text_edit.append(f"[INFO] Тепловая карта очищена\n")

    def stop_getting_data(self):
        """
        Остановка получения и записи данных
        """
        self.serial.clear()
        self.read_line_cnt = 0
        if self.stop is False:
            self.stop = True
            self.stop_button.setText("Продолжить")
            self.log_text_edit.append(f"[INFO] Процесс получения и записи данных ОСТАНОВЛЕН\n")
        elif self.stop is True:
            self.stop = False
            self.stop_button.setText("Остановить")
            self.log_text_edit.append(f"[INFO] Процесс получения и записи данных ПРОДОЛЖЕН\n")

    def confirm_sleep_time(self):
        self.sleep_time = int(self.sleep_time_input.text())
        self.log_text_edit.append(f"[INFO] Установлено время ожидания после получения пакета: {self.sleep_time} мс\n")
        self.sleep_time_input.clear()

    def showEvent(self, event):
        """
        При открытии программы
        """
        if event.type() == event.Show:
            self.refresh_ports()

        super(MainWindow, self).showEvent(event)

    def closeEvent(self, event):
        """
        При закрытии программы
        """
        if self.serial is not None and self.serial.isOpen():
            self.serial.close()

        super(MainWindow, self).closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
