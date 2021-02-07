import sys
import threading
import re
import serial
import serial.tools.list_ports
import time, os
import logging
from itertools import cycle

import keyboard

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import *
from PyQt5 import QtCore

import pystray
from PIL import Image, ImageDraw


def float_round(str_number,round_position=2):
    return str(round(float(str_number), 2))

K3PRO_BODY_TEMPERATURE_RULE = [
    ('T body = (-?\d+\.\d+).*, (.*)', lambda matched: float_round(matched[1]) if matched[2] != 'ambience compensate' else None),
]

def translate(line, translate_rules, otherwise=None):
    for pattern, translate in translate_rules:
        matched = re.search(pattern, line)
        if matched:
            return translate(matched)
    return otherwise

def extract_body_temperature(line, otherwise=None):
    return translate(line, translate_rules=K3PRO_BODY_TEMPERATURE_RULE, otherwise=otherwise)

def find_port(device_name='CH340', otherwise='COM1'):
    ports = serial.tools.list_ports.comports(include_links=False)
    for port in ports:
        if device_name in str(port):
            print ('FOUND', str(port))
            return port.device

    print ('cannot find device', device_name)
    return otherwise

def find_k3pro_port(otherwise='COM1'):
    # e.g) K3PRO => 'COM3 - USB-SERIAL CH340(COM3)'
    return find_port(device_name='CH340', otherwise=otherwise)

class FakeSerialDevice():
    def __init__(self, port='FAKE', baudrate=115200, message_seq=None, delay=1):
        self.port = port
        self.message_generator = cycle(message_seq)
        self.delay = delay
        self.is_open = True

    def readline(self):
        message = self.message_generator.__next__()
        time.sleep(self.delay)
        return message.encode()

def get_fake_serial():
        return FakeSerialDevice(message_seq=[
            'T body = 36.809 C, ambience compensate',   # ignore
            'T body = 36.614 C, weak high',             # 36.61
            'T body = 36.615, weak high',               # 36.62
            'T body = 36.626 , weak high'               # 36.63
        ])

class MainUi(QtWidgets.QMainWindow):
    connection_changed = QtCore.pyqtSignal(object)

    def __init__(self):
        super(MainUi, self).__init__()
        ui_path = resource_path('main.ui')
        print ('Load: ', ui_path)
        uic.loadUi(ui_path, self)
        self.show()
        self.init_slot_signal()

    def init_slot_signal(self):
        self.logger = logging.Logger('k3pro')
        #self.logger.setLevel(logging.INFO)
        self.logger.setLevel(logging.DEBUG)

        self.k3pro_client = K3ProClientThread(serial=None, logger=self.logger)
        self.k3pro_client.received.connect(self.text_edit.append)
        # test: disabled
        self.k3pro_client.received.connect(self.write_keyboard)
        self.k3pro_client.status.connect(self.statusBar().showMessage)

        self.connection_changed.connect(self.k3pro_client.set_serial)
        self.connection_changed.connect(lambda serial: self.combo_port.setCurrentText(serial.port))
        self.connection_changed.connect(lambda serial: self.statusBar().showMessage(self.get_serial_status(serial)))
        self.connect_button.clicked.connect(self.serial_port_changed)

        port = find_k3pro_port(otherwise=None)

        # real device: auto detect serial port by searching CH340 device
        serial = self.connect_serial(port)
        # fake device
        serial = get_fake_serial()

        # MODEL update
        self.update_serial(serial)

        self.k3pro_client.start()

    # update model
    def update_serial(self, serial):
        self.serial = serial
        self.connection_changed.emit(self.serial)

    def serial_port_changed(self):
        port = self.combo_port.currentText()
        serial = self.connect_serial(port)
        self.update_serial(serial)
    
    def connect_serial(self, port):
        self.logger.info (f'current port {port}')
        try:
            return serial.Serial(port=port, baudrate=115200)
        except Exception as e:
            self.statusBar().showMessage(f'Fail to connect {port}: {str(e)}')
            return serial.Serial()
    
    def get_serial_status(self, serial):
        return f'Connected {serial.port}' if serial.is_open else f'Disconnected'

    def write_keyboard(self, message):
        if self.checkbox_keyboard_event.isChecked():
            keyboard.write(message + '\n')
        else:
            self.logger.info('keyboard event disabled')


class K3ProClientThread(QThread):
    received = QtCore.pyqtSignal(str)
    status = QtCore.pyqtSignal(str)

    def __init__(self, parent=None, serial=None, logger=None):
        super().__init__(parent)
        self.serial = serial
        self.logger = logger

    def set_serial(self, serial):
        self.serial = serial
    
    def run(self):
        while True:
            if self.serial == None or self.serial.is_open == False:
                self.logger.info('not connected')
                #self.status.emit('Disconnected')
                QThread.sleep(3)
                continue
            try:
                line = readline(self.serial, otherwise=None)
                if line == None:
                    self.status.emit('fail to read')
                    QThread.sleep(3)
                    continue

                temperature = extract_body_temperature(line)
                if temperature:
                    self.logger.debug (f'>> temperature: {temperature}')
                    self.received.emit('\t'.join([temperature]))
                else:
                    self.logger.info('INFO:', line)
            except Exception as e:
                print (str(e))
                self.status.emit('Disconnected: ' + str(e))
                QThread.sleep(3)
                continue

def readline(comm, otherwise=''):
    try:
        return comm.readline().decode().strip()
    except UnicodeDecodeError as e:
        print ('unicode error')
        return ''
    except Exception as e:
        print (str(e))
        return otherwise


test_input = cycle(['T body = 36.562 C, week low', 'T body = 36.322 C, week low'])
def readline_fake(comm, otherwise=''):
    time.sleep(2)
    return test_input.__next__()

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
    
def repl(port='COM3', baudrate=115200):
    print ('repl')
    comm = serial.Serial(port, baudrate)
    count = 0
    while True:
        line = readline(comm, otherwise='')
        print ('>', line)
        ret = extract_body_temperature(line)
        if ret:
            temperature, classification = ret
            print (f'temperature: {temperature}, classsification: {classification}')
        else:
            print ('unknown:', line)

def run_repl():
    t = threading.Thread(target=repl)    
    t.start()
    t.join()

def run_gui():
    app = QtWidgets.QApplication(sys.argv)
    windows = MainUi()
    app.exec_()

def run_tray():
    def create_image():
        width = 32
        height = 32
        color1 = (128,128,128)
        color2 = (64,64,64)
        # Generate an image and draw a pattern
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle(
            (width // 2, 0, width, height // 2),
            fill=color2)
        dc.rectangle(
            (0, height // 2, width // 2, height),
            fill=color2)

        return image    

    icon = pystray.Icon('test name')
    icon.icon = create_image()
    icon.run()

if __name__ == '__main__':
    #run_repl()
    run_gui()
    #run_tray()
