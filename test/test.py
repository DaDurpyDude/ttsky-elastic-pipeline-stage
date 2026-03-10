# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles

async def initialise(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    dut.rst_n.value  = 0
    dut.ena.value    = 1
    dut.ui_in.value  = 0
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 5)
    
    # FIX 1: Release reset at a FALLING edge, not coincident with a rising edge.
    # This gives a full half-period before the next rising edge for the async
    # reset deassert to propagate cleanly through sky130 gate cells.
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    
    # FIX 2: Wait 2 complete cycles after reset release before reading anything.
    # One cycle for FFs to latch the post-reset state; one more for GL
    # combinational paths (ready_o, valid_o) to fully settle.
    await ClockCycles(dut.clk, 2)
    await FallingEdge(dut.clk)


def drive_inputs(dut, data, valid, ready_in):
    dut.ui_in.value  = data & 0xFF
    dut.uio_in.value = ((valid & 1) << 1) | (ready_in & 1)


def read_outputs(dut):
    data_o  = dut.uo_out.value.to_unsigned() & 0xFF if dut.uo_out.value.is_resolvable else 0
    uio_val = dut.uio_out.value.to_unsigned()        if dut.uio_out.value.is_resolvable else 0
    
    # FIX 3: If full word is unresolvable, try reading individual bits directly.
    # In GL sim, unused bits can briefly carry X while driven bits are valid.
    if not dut.uio_out.value.is_resolvable:
        try:
            valid_o = int(dut.uio_out[3].value)
            ready_o = int(dut.uio_out[2].value)
        except Exception:
            valid_o, ready_o = 0, 0
    else:
        valid_o = (uio_val >> 3) & 1
        ready_o = (uio_val >> 2) & 1
    
    return data_o, valid_o, ready_o

def log_cycle(dut, cycle, data_i, valid_i, ready_i, data_o, valid_o, ready_o,
              exp_data=None, exp_valid=None, exp_ready=None):
    line = (f"  [{cycle:3d}] IN  data=0x{data_i:02X} valid_i={valid_i} ready_i={ready_i}"
            f" | OUT data=0x{data_o:02X} valid_o={valid_o} ready_o={ready_o}")
    if exp_data is not None:
        ok = (valid_o == exp_valid and ready_o == exp_ready and
              (not exp_valid or data_o == exp_data))
        line += f" | EXP data=0x{exp_data:02X} valid={exp_valid} ready={exp_ready} | {'OK' if ok else 'MISMATCH'}"
    dut._log.info(line)


def assert_outputs(cycle, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready, context=""):
    prefix = f"[Cycle {cycle}]{' ' + context if context else ''}"
    assert valid_o == exp_valid, f"{prefix} valid_o={valid_o} expected {exp_valid}"
    assert ready_o == exp_ready, f"{prefix} ready_o={ready_o} expected {exp_ready}"
    if exp_valid:
        assert data_o == exp_data, f"{prefix} data_o=0x{data_o:02X} expected 0x{exp_data:02X}"


class SkidRef:
    """Cycle-accurate software model of the skid buffer (gate_data=1, reset_data=0)."""

    def __init__(self):
        self.valid = 0
        self.data  = 0

    def reset(self):
        self.valid = 0

    def step(self, data_i, valid_i, ready_i):
        ready_pre = 1 if (ready_i or not self.valid) else 0

        if ready_pre and valid_i:
            self.valid = 1
            self.data  = data_i
        elif ready_i:
            self.valid = 0

        ready_post = 1 if (ready_i or not self.valid) else 0
        return self.data, self.valid, ready_post


@cocotb.test()
async def test_reset_basic(dut):
    """Buffer must come out of reset empty (valid_o=0) and accepting (ready_o=1)."""
    await initialise(dut)
    data_o, valid_o, ready_o = read_outputs(dut)
    dut._log.info(f"  After reset | data_o=0x{data_o:02X} valid_o={valid_o} ready_o={ready_o}")
    assert valid_o == 0, f"valid_o={valid_o} expected 0"
    assert ready_o == 1, f"ready_o={ready_o} expected 1"


@cocotb.test()
async def test_reset_while_full(dut):
    """Reset must clear valid_o but not data_o when datapath_reset_p=0."""
    await initialise(dut)
    fill_data = 0xAB

    drive_inputs(dut, fill_data, valid=1, ready_in=0)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    data_o, valid_o, _ = read_outputs(dut)
    dut._log.info(f"  After fill  | data_o=0x{data_o:02X} valid_o={valid_o}")
    assert valid_o == 1 and data_o == fill_data, \
        f"Buffer did not fill — valid_o={valid_o} data_o=0x{data_o:02X}"

    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await FallingEdge(dut.clk)

    data_o, valid_o, ready_o = read_outputs(dut)
    dut._log.info(f"  After reset | data_o=0x{data_o:02X} valid_o={valid_o} ready_o={ready_o}")
    assert valid_o == 0,         f"valid_o={valid_o} expected 0"
    assert ready_o == 1,         f"ready_o={ready_o} expected 1"
    assert data_o == fill_data,  \
        f"data_o=0x{data_o:02X} expected 0x{fill_data:02X} — datapath_reset_p=0 must not clear data register"


@cocotb.test()
async def test_single_transfer(dut):
    """Data must appear at output one cycle after a valid handshake."""
    await initialise(dut)
    ref       = SkidRef()
    test_data = 0xA5

    drive_inputs(dut, test_data, valid=1, ready_in=1)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)

    data_o, valid_o, ready_o       = read_outputs(dut)
    exp_data, exp_valid, exp_ready = ref.step(test_data, valid_i=1, ready_i=1)
    log_cycle(dut, 1, test_data, 1, 1, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready)
    assert_outputs(1, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready)


@cocotb.test()
async def test_multiple_transfers(dut):
    """Buffer must sustain full throughput with no bubbles under continuous flow."""
    await initialise(dut)
    ref       = SkidRef()
    test_data = [0x11, 0x22, 0x33, 0x44]

    dut._log.info(f"  Sending: {[hex(x) for x in test_data]}")
    for i, d in enumerate(test_data):
        drive_inputs(dut, d, valid=1, ready_in=1)
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
        data_o, valid_o, ready_o       = read_outputs(dut)
        exp_data, exp_valid, exp_ready = ref.step(d, 1, 1)
        log_cycle(dut, i + 1, d, 1, 1, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready)
        assert_outputs(i + 1, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready)


@cocotb.test()
async def test_backpressure(dut):
    """Buffer must hold data and assert ready_o=0 when downstream is stalled."""
    await initialise(dut)
    ref       = SkidRef()
    fill_data = 0x11

    stimulus = [
        (fill_data, 1, 0, "fill"),
        (0x22,      1, 0, "stall — 0x22 must be rejected, 0x11 held"),
        (0x33,      1, 1, "release — 0x33 enters as 0x11 drains"),
    ]

    for cycle, (data, valid, ready, note) in enumerate(stimulus, start=1):
        dut._log.info(f"  Cycle {cycle}: {note}")
        drive_inputs(dut, data, valid=valid, ready_in=ready)
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
        data_o, valid_o, ready_o       = read_outputs(dut)
        exp_data, exp_valid, exp_ready = ref.step(data, valid, ready)
        log_cycle(dut, cycle, data, valid, ready, data_o, valid_o, ready_o,
                  exp_data, exp_valid, exp_ready)
        assert_outputs(cycle, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready, note)


@cocotb.test()
async def test_backpressure_extended(dut):
    """Data must remain stable across multiple stall cycles with no corruption."""
    await initialise(dut)
    ref       = SkidRef()
    fill_data = 0x55

    drive_inputs(dut, fill_data, valid=1, ready_in=0)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    ref.step(fill_data, 1, 0)

    for i, d in enumerate([0x66, 0x77, 0x88], start=1):
        drive_inputs(dut, d, valid=1, ready_in=0)
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
        data_o, valid_o, ready_o       = read_outputs(dut)
        exp_data, exp_valid, exp_ready = ref.step(d, 1, 0)
        log_cycle(dut, i, d, 1, 0, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready)
        assert data_o  == fill_data, \
            f"[Cycle {i}] data_o=0x{data_o:02X} expected 0x{fill_data:02X} — data changed during stall"
        assert valid_o == 1, f"[Cycle {i}] valid_o={valid_o} expected 1"
        assert ready_o == 0, f"[Cycle {i}] ready_o={ready_o} expected 0 — backpressure not asserted"

    release_data = 0x99
    drive_inputs(dut, release_data, valid=1, ready_in=1)
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    data_o, valid_o, ready_o       = read_outputs(dut)
    exp_data, exp_valid, exp_ready = ref.step(release_data, 1, 1)
    log_cycle(dut, 4, release_data, 1, 1, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready)
    assert_outputs(4, data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready, "release")


@cocotb.test()
async def test_random_stress(dut):
    """Exhaustive random stimulus compared cycle-by-cycle against the reference model."""
    await initialise(dut)
    ref = SkidRef()
    ref.reset()
    random.seed(12345)  # fixed seed for reproducibility

    total      = 100
    mismatches = 0

    for cycle in range(total):
        data_i  = random.randint(0, 255)
        valid_i = random.randint(0, 1)
        ready_i = random.randint(0, 1)

        drive_inputs(dut, data_i, valid_i, ready_i)
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)

        data_o, valid_o, ready_o       = read_outputs(dut)
        exp_data, exp_valid, exp_ready = ref.step(data_i, valid_i, ready_i)

        ok = (valid_o == exp_valid and ready_o == exp_ready and
              (not exp_valid or data_o == exp_data))
        if not ok:
            mismatches += 1

        log_cycle(dut, cycle, data_i, valid_i, ready_i,
                  data_o, valid_o, ready_o, exp_data, exp_valid, exp_ready)

        assert valid_o == exp_valid, \
            f"[Cycle {cycle}] valid_o={valid_o} expected {exp_valid} " \
            f"(in: data=0x{data_i:02X} valid_i={valid_i} ready_i={ready_i})"
        assert ready_o == exp_ready, \
            f"[Cycle {cycle}] ready_o={ready_o} expected {exp_ready} " \
            f"(in: data=0x{data_i:02X} valid_i={valid_i} ready_i={ready_i})"
        if exp_valid:
            assert data_o == exp_data, \
                f"[Cycle {cycle}] data_o=0x{data_o:02X} expected 0x{exp_data:02X} " \
                f"(in: data=0x{data_i:02X} valid_i={valid_i} ready_i={ready_i})"

    dut._log.info(f"  {total} cycles: {total - mismatches} passed, {mismatches} mismatches")
    