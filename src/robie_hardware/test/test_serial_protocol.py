from robie_hardware.serial_protocol import (
    encode_enable, encode_motor_cmd, parse_line)


def test_encode_motor():
    assert encode_motor_cmd((1.0, 2.0, 3.0, 4.0)) == 'M,1.000,2.000,3.000,4.000'


def test_encode_enable():
    assert encode_enable(True) == 'S,1'
    assert encode_enable(False) == 'S,0'


def test_parse_t_frame():
    p = parse_line('T,1,0,1')
    assert p['estop'] is True
    assert p['bumper_front'] is False
    assert p['bumper_rear'] is True


def test_parse_h_frame():
    assert parse_line('H,12345')['millis'] == 12345


def test_parse_boot_and_garbage():
    assert parse_line('H,ROBIE_FW_V1_BOOT') is None
    assert parse_line('T,1,0') is None
    assert parse_line('X,9') is None
