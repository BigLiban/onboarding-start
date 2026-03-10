# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
import cocotb.utils
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.triggers import FallingEdge
from cocotb.triggers import Timer
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")




@cocotb.test()
async def test_pwm_freq(dut):
    dut._log.info("PWM Frequency test")

    clock = Clock(dut.clk, 100, units="ns")  # 10 MHz clock
    cocotb.start_soon(clock.start())

    # Reset
    dut.ena.value = 1
    dut.ui_in.value = ui_in_logicarray(1, 0, 0)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Enable output on bit 0 of uo_out (register 0x00 = 0xFF)
    await send_spi_transaction(dut, 1, 0x00, 0xFF)
    # Enable PWM mode on bit 0 (register 0x02 = 0xFF)
    await send_spi_transaction(dut, 1, 0x02, 0xFF)
    # Set 50% duty cycle for clean measurement
    await send_spi_transaction(dut, 1, 0x04, 0x80)
    await ClockCycles(dut.clk, 500)

    # Measure period between two rising edges on uo_out bit 0
    # Wait for first rising edge
    timeout_cycles = 1_000_000
    elapsed = 0
    # Wait until signal is low first
    while dut.uo_out.value.integer & 0x01:
        await RisingEdge(dut.clk)
        elapsed += 1
        assert elapsed < timeout_cycles, "Timeout waiting for signal to go low"

    # Wait for first rising edge
    elapsed = 0
    while not (dut.uo_out.value.integer & 0x01):
        await RisingEdge(dut.clk)
        elapsed += 1
        assert elapsed < timeout_cycles, "Timeout waiting for first rising edge"
    t_rise1 = cocotb.utils.get_sim_time(units="ns")

    # Wait for second rising edge (go low first, then high)
    elapsed = 0
    while dut.uo_out.value.integer & 0x01:
        await RisingEdge(dut.clk)
        elapsed += 1
        assert elapsed < timeout_cycles, "Timeout waiting for falling edge"

    elapsed = 0
    while not (dut.uo_out.value.integer & 0x01):
        await RisingEdge(dut.clk)
        elapsed += 1
        assert elapsed < timeout_cycles, "Timeout waiting for second rising edge"
    t_rise2 = cocotb.utils.get_sim_time(units="ns")

    period_ns = t_rise2 - t_rise1
    freq_hz = 1e9 / period_ns

    dut._log.info(f"Measured period: {period_ns:.1f} ns, frequency: {freq_hz:.1f} Hz")

    # Check frequency is 3 kHz ± 1%
    target_freq = 3000.0
    tolerance = 0.01
    assert abs(freq_hz - target_freq) / target_freq <= tolerance, \
        f"Frequency {freq_hz:.1f} Hz out of ±1% tolerance of {target_freq} Hz"

    dut._log.info("PWM Frequency test completed successfully")


@cocotb.test()
async def test_pwm_duty(dut):
    dut._log.info("PWM Duty Cycle test")

    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut.ena.value = 1
    dut.ui_in.value = ui_in_logicarray(1, 0, 0)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Enable output and PWM mode
    await send_spi_transaction(dut, 1, 0x00, 0xFF)
    await send_spi_transaction(dut, 1, 0x02, 0xFF)

    async def measure_duty_cycle(dut, timeout_cycles=2_000_000):
        """Measure duty cycle by timing high vs full period on uo_out bit 0."""
        # Ensure signal is not stuck (handle 0% and 100% edge cases)
        # Wait until low
        elapsed = 0
        while dut.uo_out.value.integer & 0x01:
            await RisingEdge(dut.clk)
            elapsed += 1
            if elapsed >= timeout_cycles:
                # Signal never went low -> 100% duty cycle
                return 100.0

        # Wait for rising edge (start of period)
        elapsed = 0
        while not (dut.uo_out.value.integer & 0x01):
            await RisingEdge(dut.clk)
            elapsed += 1
            if elapsed >= timeout_cycles:
                # Signal never went high -> 0% duty cycle
                return 0.0
        t_rise = cocotb.utils.get_sim_time(units="ns")

        # Wait for falling edge
        elapsed = 0
        while dut.uo_out.value.integer & 0x01:
            await RisingEdge(dut.clk)
            elapsed += 1
            if elapsed >= timeout_cycles:
                return 100.0  # Stuck high
        t_fall = cocotb.utils.get_sim_time(units="ns")

        # Wait for next rising edge (end of period)
        elapsed = 0
        while not (dut.uo_out.value.integer & 0x01):
            await RisingEdge(dut.clk)
            elapsed += 1
            if elapsed >= timeout_cycles:
                return 0.0  # Stuck low
        t_rise2 = cocotb.utils.get_sim_time(units="ns")

        high_time = t_fall - t_rise
        period = t_rise2 - t_rise
        return (high_time / period) * 100.0

    tolerance = 1.0  # ±1%

    # Test cases: (register_value, expected_duty_cycle_percent)
    test_cases = [
        (0x00, 0.0),    # 0% - always low
        (0x80, 50.0),   # ~50% (128/256 * 100)
        (0xFF, 100.0),  # 100% - always high
        (0x40, 25.0),   # ~25% (64/256 * 100)
        (0xC0, 75.0),   # ~75% (192/256 * 100)
    ]

    for reg_val, expected_duty in test_cases:
        dut._log.info(f"Testing duty cycle register=0x{reg_val:02X}, expected={expected_duty:.1f}%")
        await send_spi_transaction(dut, 1, 0x04, reg_val)
        # Allow PWM to stabilize for a couple periods
        await ClockCycles(dut.clk, 5000)

        measured = await measure_duty_cycle(dut)
        dut._log.info(f"  Measured duty cycle: {measured:.2f}%")

        assert abs(measured - expected_duty) <= tolerance, \
            f"Duty cycle for reg=0x{reg_val:02X}: expected {expected_duty:.1f}%, " \
            f"got {measured:.2f}% (tolerance ±{tolerance}%)"

    dut._log.info("PWM Duty Cycle test completed successfully")
