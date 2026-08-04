import unittest

from wavebench_rigol_dg1000 import descriptor
from wavebench_rigol_dg1000.driver import DG1000Source
from wavebench.errors import DataError


class FakeDG1000Transport:
    def __init__(self):
        self.writes = []
        self.queries = []
        self.error_queue = ['0,"No error"']
        self.state = {
            1: {
                "out": "OFF",
                "func": "SIN",
                "freq": 1000.0,
                "volt": 1.0,
                "unit": "VPP",
                "offs": 0.0,
                "phas": 0.0,
                "duty": 50.0,
                "apply": 'CH1:"SIN,1.000000e+03,1.000000e+00,0.000000e+00"',
            },
            2: {
                "out": "ON",
                "func": "RAMP",
                "freq": 1500.0,
                "volt": 2.0,
                "unit": "VPP",
                "offs": 0.5,
                "phas": 10.0,
                "duty": 30.0,
                "apply": 'CH2:"RAMP,1.500000e+03,2.000000e+00,5.000000e-01"',
            },
        }
        self.sweep = "OFF"

    def write(self, command: str) -> None:
        self.writes.append(command)
        if command == "SWE:STAT OFF":
            self.sweep = "OFF"
            return
        channel, key, value = self._parse_write(command)
        if key == "out":
            self.state[channel]["out"] = value
        elif key == "func":
            self.state[channel]["func"] = value
        elif key == "freq":
            self.state[channel]["freq"] = float(value)
        elif key == "unit":
            self.state[channel]["unit"] = value
        elif key == "volt":
            self.state[channel]["volt"] = float(value)
        elif key == "duty":
            self.state[channel]["duty"] = float(value)

    def _parse_write(self, command: str):
        parts = command.split()
        head = parts[0]
        value = parts[1]
        if head == "OUTP":
            return 1, "out", value
        if head == "OUTP:CH2":
            return 2, "out", value
        if head == "FUNC":
            return 1, "func", value
        if head == "FUNC:CH2":
            return 2, "func", value
        if head == "FREQ":
            return 1, "freq", value
        if head == "FREQ:CH2":
            return 2, "freq", value
        if head == "VOLT:UNIT":
            return 1, "unit", value
        if head == "VOLT:UNIT:CH2":
            return 2, "unit", value
        if head == "VOLT":
            return 1, "volt", value
        if head == "VOLT:CH2":
            return 2, "volt", value
        if head == "FUNC:SQU:DCYC":
            return 1, "duty", value
        if head == "FUNC:SQU:DCYC:CH2":
            return 2, "duty", value
        raise AssertionError(f"unexpected write {command!r}")

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command == "*IDN?":
            return "Rigol Technologies,DG1022,SN,FW"
        if command == "SYST:ERR?":
            if self.error_queue:
                return self.error_queue.pop(0)
            return '0,"No error"'
        if command == "SWE:STAT?":
            return self.sweep
        if command == "APPL?":
            return self.state[1]["apply"]
        if command == "APPL:CH2?":
            return self.state[2]["apply"]
        for channel in (1, 2):
            prefix = "" if channel == 1 else ":CH2"
            state = self.state[channel]
            mapping = {
                f"OUTP{prefix}?": state["out"],
                f"FUNC{prefix}?": f"CH{channel}:{state['func']}",
                f"FREQ{prefix}?": (
                    str(state["freq"]) if channel == 1 else f"CH2:{state['freq']}"
                ),
                f"VOLT{prefix}?": (
                    str(state["volt"]) if channel == 1 else f"CH2:{state['volt']}"
                ),
                f"VOLT:UNIT{prefix}?": state["unit"],
                f"VOLT:OFFS{prefix}?": (
                    str(state["offs"]) if channel == 1 else f"CH2:{state['offs']}"
                ),
                f"PHAS{prefix}?": str(state["phas"]),
                f"FUNC:SQU:DCYC{prefix}?": str(state["duty"]),
            }
            if command in mapping:
                return mapping[command]
        raise AssertionError(f"unexpected query {command!r}")

    def close(self) -> None:
        pass


class FakeDG1000ZTransport:
    def __init__(self):
        self.writes = []
        self.queries = []
        self.error_queue = ['0,"No error"']
        self.state = {
            1: {
                "out": "OFF",
                "func": "SIN",
                "freq": 1000.0,
                "volt": 1.0,
                "unit": "VPP",
                "offs": 0.0,
                "phas": 0.0,
                "duty": 50.0,
                "apply": '"SIN,1.000000E+03,1.000000E+00,0.000000E+00,0.000000E+00"',
                "sweep": "OFF",
            },
            2: {
                "out": "ON",
                "func": "RAMP",
                "freq": 50000.0,
                "volt": 1.0,
                "unit": "VPP",
                "offs": 0.5,
                "phas": 0.0,
                "duty": 30.0,
                "apply": '"RAMP,5.000000E+04,1.000000E+00,5.000000E-01,0.000000E+00"',
                "sweep": "OFF",
            },
        }

    def write(self, command: str) -> None:
        self.writes.append(command)
        parts = command.split()
        head = parts[0]
        value = parts[1]
        for channel in (1, 2):
            prefix = f":SOUR{channel}:"
            if head == f":OUTP{channel}":
                self.state[channel]["out"] = value
                return
            if head == f"{prefix}FUNC":
                self.state[channel]["func"] = value
                return
            if head == f"{prefix}FREQ":
                self.state[channel]["freq"] = float(value)
                return
            if head == f"{prefix}VOLT:UNIT":
                self.state[channel]["unit"] = value
                return
            if head == f"{prefix}VOLT":
                self.state[channel]["volt"] = float(value)
                return
            if head == f"{prefix}FUNC:SQU:DCYC":
                self.state[channel]["duty"] = float(value)
                return
            if head == f"{prefix}SWE:STAT":
                self.state[channel]["sweep"] = value
                return
        raise AssertionError(f"unexpected write {command!r}")

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command == "*IDN?":
            return "Rigol Technologies,DG1032Z,SN,06.01.13"
        if command == "SYST:ERR?":
            if self.error_queue:
                return self.error_queue.pop(0)
            return '0,"No error"'
        for channel in (1, 2):
            state = self.state[channel]
            prefix = f":SOUR{channel}:"
            mapping = {
                f":OUTP{channel}?": state["out"],
                f"{prefix}FUNC?": state["func"],
                f"{prefix}FREQ?": str(state["freq"]),
                f"{prefix}VOLT?": str(state["volt"]),
                f"{prefix}VOLT:UNIT?": state["unit"],
                f"{prefix}VOLT:OFFS?": str(state["offs"]),
                f"{prefix}PHAS?": str(state["phas"]),
                f"{prefix}SWE:STAT?": state["sweep"],
                f"{prefix}FUNC:SQU:DCYC?": str(state["duty"]),
                f"{prefix}APPL?": state["apply"],
            }
            if command in mapping:
                return mapping[command]
        raise AssertionError(f"unexpected query {command!r}")

    def close(self) -> None:
        pass


class DG1000Tests(unittest.TestCase):
    def test_descriptor_exposes_basic_dg1000_source_capabilities(self):
        plugin = descriptor()

        self.assertEqual(plugin.driver_id, "rigol.dg1000")
        self.assertEqual(plugin.kind, "source")
        self.assertEqual(plugin.distribution, "wavebench-rigol-dg1000")
        self.assertIn("DG1022", plugin.models)
        self.assertIn("DG1032Z", plugin.models)
        self.assertIn("source.status", plugin.capabilities)
        self.assertIn("source.set_frequency", plugin.capabilities)
        self.assertNotIn("source.arbitrary_upload", plugin.capabilities)

    def test_get_status_reads_channel_two_with_dg1000_command_layout(self):
        transport = FakeDG1000Transport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.get_status(2)

        self.assertEqual(status.channel, 2)
        self.assertEqual(status.output, "ON")
        self.assertEqual(status.function, "RAMP")
        self.assertEqual(status.frequency_hz, 1500.0)
        self.assertEqual(status.amplitude, 2.0)
        self.assertEqual(status.offset_v, 0.5)
        self.assertEqual(status.frequency_mode, "FIX")
        self.assertEqual(status.sweep_enabled, "OFF")
        self.assertEqual(status.square_duty_cycle_percent, 30.0)

    def test_get_status_reads_channel_two_with_dg1000z_source_layout(self):
        transport = FakeDG1000ZTransport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.get_status(2)

        self.assertEqual(status.channel, 2)
        self.assertEqual(status.output, "ON")
        self.assertEqual(status.function, "RAMP")
        self.assertEqual(status.frequency_hz, 50000.0)
        self.assertEqual(status.amplitude, 1.0)
        self.assertEqual(status.offset_v, 0.5)
        self.assertEqual(status.frequency_mode, "FIX")
        self.assertEqual(status.sweep_enabled, "OFF")
        self.assertEqual(status.square_duty_cycle_percent, 30.0)
        self.assertIn(":OUTP2?", transport.queries)
        self.assertIn(":SOUR2:FUNC?", transport.queries)
        self.assertIn(":SOUR2:APPL?", transport.queries)

    def test_rejects_channel_outside_dg1000_dual_channel_range_before_io(self):
        transport = FakeDG1000Transport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        with self.assertRaisesRegex(DataError, "DG1000 channel must be 1 or 2"):
            driver.get_status(3)

        self.assertEqual(transport.writes, [])

    def test_set_channel_two_frequency_uses_dg1000_ch2_suffix(self):
        transport = FakeDG1000Transport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_frequency(2, 2000.0, check_errors=True)

        self.assertEqual(transport.writes[0], "FREQ:CH2 2000")
        self.assertEqual(status.frequency_hz, 2000.0)

    def test_set_channel_one_frequency_disables_sweep_when_requested(self):
        transport = FakeDG1000Transport()
        transport.sweep = "ON"
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_frequency(1, 2000.0, ensure_fix_mode=True, check_errors=True)

        self.assertEqual(transport.writes[:2], ["SWE:STAT OFF", "FREQ 2000"])
        self.assertEqual(status.frequency_mode, "FIX")

    def test_set_channel_two_frequency_uses_dg1000z_source_layout_and_disables_sweep(self):
        transport = FakeDG1000ZTransport()
        transport.state[2]["sweep"] = "ON"
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_frequency(2, 2000.0, ensure_fix_mode=True, check_errors=True)

        self.assertEqual(transport.writes[:2], [":SOUR2:SWE:STAT OFF", ":SOUR2:FREQ 2000"])
        self.assertEqual(status.frequency_hz, 2000.0)
        self.assertEqual(status.frequency_mode, "FIX")

    def test_set_function_writes_normalized_dg1000_function(self):
        transport = FakeDG1000Transport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_function(2, "triangle", check_errors=True)

        self.assertEqual(transport.writes[0], "FUNC:CH2 RAMP")
        self.assertEqual(status.function, "RAMP")

    def test_set_amplitude_vpp_sets_channel_specific_unit_and_amplitude(self):
        transport = FakeDG1000Transport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_amplitude_vpp(2, 3.3, check_errors=True)

        self.assertEqual(transport.writes[:2], ["VOLT:UNIT:CH2 VPP", "VOLT:CH2 3.3"])
        self.assertEqual(status.amplitude, 3.3)
        self.assertEqual(status.amplitude_unit, "VPP")

    def test_set_amplitude_vpp_uses_dg1000z_source_layout(self):
        transport = FakeDG1000ZTransport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_amplitude_vpp(2, 3.3, check_errors=True)

        self.assertEqual(transport.writes[:2], [":SOUR2:VOLT:UNIT VPP", ":SOUR2:VOLT 3.3"])
        self.assertEqual(status.amplitude, 3.3)
        self.assertEqual(status.amplitude_unit, "VPP")

    def test_set_square_duty_cycle_uses_channel_specific_dg1000_command(self):
        transport = FakeDG1000Transport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_square_duty_cycle(2, 25.0, check_errors=True)

        self.assertEqual(transport.writes[0], "FUNC:SQU:DCYC:CH2 25")
        self.assertEqual(status.square_duty_cycle_percent, 25.0)

    def test_set_square_duty_cycle_uses_dg1000z_source_layout(self):
        transport = FakeDG1000ZTransport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_square_duty_cycle(2, 25.0, check_errors=True)

        self.assertEqual(transport.writes[0], ":SOUR2:FUNC:SQU:DCYC 25")
        self.assertEqual(status.square_duty_cycle_percent, 25.0)

    def test_set_output_writes_dg1000_channel_output(self):
        transport = FakeDG1000Transport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_output(2, False, check_errors=True)

        self.assertEqual(transport.writes[0], "OUTP:CH2 OFF")
        self.assertEqual(status.output, "OFF")

    def test_set_output_uses_dg1000z_source_layout(self):
        transport = FakeDG1000ZTransport()
        driver = DG1000Source(transport=transport, check_errors_after_ops=True)

        status = driver.set_output(2, False, check_errors=True)

        self.assertEqual(transport.writes[0], ":OUTP2 OFF")
        self.assertEqual(status.output, "OFF")


if __name__ == "__main__":
    unittest.main()
