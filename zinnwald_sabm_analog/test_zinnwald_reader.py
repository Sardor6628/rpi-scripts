from zinnwald_reader import sensor_status


def test_floating_open_circuit_is_fault():
    status = sensor_status(1.435, sample_spread=0.72)
    assert status.startswith("FAULT")


def test_valid_low_h2_voltage_is_ok():
    status = sensor_status(1.0, sample_spread=0.02)
    assert status == "OK"
