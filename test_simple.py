import pytest
import keyboard
import time

#from apps.main import extract_body_temperature
from main import extract_body_temperature 

# exmaple log
'''
    b'Proximity: 947'
    b'Close'
    b'===================================='
    b'times = 805'
    b'ad = 1532'
    b'times = 807'
    b'ad = 1648'
    b'1240.000'
    b'1333.890'
    b'vs = 93.890'
    b'vs = 221.189, calibrate modify'
    b'vs = 225.845, emissivity compensate'
    b'to1 = 34.292'
    b'to2 = 35.238'
    b'T Object = 34.320 C'
    b'T body = 36.809 C, ambience compensate'
    b'T body = 36.694 C, weak high'
    b'cfg.mode = 0'
    b'U\xaa\x07\x04o'
    b'L'
    b'Proximity: 228'
    b'Away'
'''

def test_body_temperature():
    tests = [
        (None,                    'T body = 36.809 C, ambience compensate'),
        (('36.694', 'weak high'), 'T body = 36.694 C, weak high')
    ]
    for expected, line in tests:
        actual = extract_body_temperature(line, None)
        assert expected == actual

def test_gen_keyevents():
    events = '36.694'
    print (f'key events: {events}')
    keyboard.write(events)

def test_discover_com_port():
    pass
    
    
