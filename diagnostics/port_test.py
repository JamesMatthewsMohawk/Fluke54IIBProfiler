"""Phase 1 environment validation for Fluke 54 II B IRUSB communication discovery.

Verifies Python version, pyserial availability, COM3 presence, and that the
port can be opened with the documented serial settings (9600 8N1, no flow control).
"""
from __future__ import annotations

import sys

REQUIRED_PORT = "COM3"
REQUIRED_BAUD = 9600


def check_python_version() -> bool:
    ok = sys.version_info >= (3, 12)
    print(f"PYTHON VERSION: {sys.version.split()[0]} {'OK' if ok else 'FAIL (requires 3.12+)'}")
    return ok


def check_pyserial() -> bool:
    try:
        import serial
        print(f"PYSERIAL: {serial.__version__} OK")
        return True
    except ImportError as e:
        print(f"PYSERIAL: MISSING ({e})")
        return False


def check_com3_exists() -> bool:
    import serial.tools.list_ports as list_ports

    ports = {p.device: p for p in list_ports.comports()}
    if REQUIRED_PORT in ports:
        p = ports[REQUIRED_PORT]
        print(f"{REQUIRED_PORT} FOUND ({p.description}, {p.hwid})")
        return True
    print(f"{REQUIRED_PORT} NOT FOUND. Available ports: {list(ports.keys())}")
    return False


def check_com3_opens() -> bool:
    import serial
    from serial import SerialException

    try:
        with serial.Serial(
            port=REQUIRED_PORT,
            baudrate=REQUIRED_BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
            timeout=1,
        ) as ser:
            settings_ok = (
                ser.baudrate == REQUIRED_BAUD
                and ser.bytesize == serial.EIGHTBITS
                and ser.parity == serial.PARITY_NONE
                and ser.stopbits == serial.STOPBITS_ONE
                and not ser.xonxoff
                and not ser.rtscts
                and not ser.dsrdtr
            )
            print("PORT OPEN SUCCESS")
            if settings_ok:
                print(f"{REQUIRED_BAUD} 8N1 ACTIVE")
            else:
                print(f"{REQUIRED_BAUD} 8N1 MISMATCH: actual baud={ser.baudrate} "
                      f"bytesize={ser.bytesize} parity={ser.parity} stopbits={ser.stopbits} "
                      f"xonxoff={ser.xonxoff} rtscts={ser.rtscts} dsrdtr={ser.dsrdtr}")
            return settings_ok
    except SerialException as e:
        print(f"PORT OPEN FAIL: {type(e).__name__}: {e}")
        return False


def main() -> int:
    results = [
        check_python_version(),
        check_pyserial(),
        check_com3_exists(),
        check_com3_opens(),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
