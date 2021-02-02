import sys
import threading
import re
import serial
import serial.tools.list_ports
import time, os

import keyboard

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import *
from PyQt5 import QtCore

def extract_body_temperature(line, otherwise=None):
    pattern = 'T body = (-?\d+\.\d+) C, (.*)'
    matched = re.search(pattern, line)
    return (matched[1], matched[2]) if matched and matched[2] != 'ambience compensate' else otherwise

def find_port(device_name='CH340', otherwise='COM1'):
    ports = serial.tools.list_ports.comports(include_links=False)
    for port in ports:
        if device_name in str(port):
            print ('FOUND', str(port))
            return port.device

    print ('cannot found device', device_name)
    return otherwise

def find_k3pro_port(otherwise='COM1'):
    # e.g) K3PRO => 'COM3 - USB-SERIAL CH340(COM3)'
    return find_port(device_name='CH340', otherwise=otherwise)
    
class MainUi(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainUi, self).__init__()
        ui_path = resource_path('main.ui')
        print ('Load: ', ui_path)
        uic.loadUi(ui_path, self)
        self.statusBar().showMessage('Init')
        self.show()

        self.k3pro_client = K3ProClientThread(port='COM1')
        self.k3pro_client.received.connect(self.text_edit.append)
        self.k3pro_client.status.connect(self.statusBar().showMessage)

        port = find_k3pro_port(otherwise='COM1')
        self.combo_port.setCurrentText(port)
        self.k3pro_client.set_port(port)

        self.combo_port.currentTextChanged.connect(self.k3pro_client.set_port)
        self.k3pro_client.start()
    
class K3ProClientThread(QThread):
    received = QtCore.pyqtSignal(str)
    status = QtCore.pyqtSignal(str)

    def __init__(self, port='COM1', baudrate=115200, parent=None):
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate

    def set_port(self, port):
        self.port = port

    def run(self):
        while True:
            try:
                comm = serial.Serial(port=self.port, baudrate=self.baudrate)
                self.status.emit(f'Connected {self.port}')
            except Exception as e:
                print (str(e))
                self.status.emit('Error: ' + str(e))
                QThread.sleep(3) # 3 second

                port = find_k3pro_port()
                self.set_port(port)
                continue

            while True:
                line = readline(comm, otherwise=None)
                if line == None:
                    print ('Disconnected?')
                    comm.close()
                    break

                ret = extract_body_temperature(line)
                if ret:
                    temperature, classification = ret
                    temperature = str(round(float(temperature),2))
                    print (f'>> temperature: {temperature}')
                    self.received.emit('\t'.join([temperature, classification]))
                    keyboard.write(temperature + '\n')
                else:
                    print ('INFO:', line)

def readline(comm, otherwise=''):
    try:
        return comm.readline().decode().strip()
    except UnicodeDecodeError as e:
        print ('unicode error')
        return ''
    except Exception as e:
        print (str(e))
        return otherwise

from itertools import cycle
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

if __name__ == '__main__':
    #run_repl()
    run_gui()
