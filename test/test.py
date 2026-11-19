# SPDX-FileCopyrightText: © 2026 Rohtak Patwardhan
# SPDX-License-Identifier: Apache-2.0

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

CLKS_PER_BIT = 434          # must match project.sv (50 MHz / 115200)
FRAME_CLKS = 10 * CLKS_PER_BIT


def tx(dut):
    return int(dut.uo_out.value) & 1


def busy(dut):
    return (int(dut.uo_out.value) >> 1) & 1


async def reset(dut):
    clock = Clock(dut.clk, 20, unit="ns")   # 50 MHz
    cocotb.start_soon(clock.start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


async def press_send(dut, hold=5):
    dut.uio_in.value = 1
    await ClockCycles(dut.clk, hold)
    dut.uio_in.value = 0


async def uart_receive(dut, timeout=1000):
    """Decode one 8N1 frame from uo_out[0], sampling mid-bit."""
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if tx(dut) == 0:
            break
    else:
        raise AssertionError("no start bit detected")

    await ClockCycles(dut.clk, CLKS_PER_BIT // 2)
    assert tx(dut) == 0, "start bit not held low"

    byte = 0
    for i in range(8):
        await ClockCycles(dut.clk, CLKS_PER_BIT)
        byte |= tx(dut) << i                 # LSB first

    await ClockCycles(dut.clk, CLKS_PER_BIT)
    assert tx(dut) == 1, "stop bit not high"
    return byte


async def wait_idle(dut, timeout=FRAME_CLKS):
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if busy(dut) == 0:
            return
    raise AssertionError("BUSY never deasserted")


@cocotb.test()
async def test_idle_after_reset(dut):
    await reset(dut)
    assert tx(dut) == 1, "TX should idle high"
    assert busy(dut) == 0, "BUSY should be low after reset"


@cocotb.test()
async def test_send_bytes(dut):
    await reset(dut)
    vectors = [0x41, 0x00, 0xFF, 0x55, 0xAA] + [random.randrange(256) for _ in range(10)]

    for value in vectors:
        dut.ui_in.value = value
        await ClockCycles(dut.clk, 2)
        await press_send(dut)
        got = await uart_receive(dut)
        assert got == value, f"sent 0x{value:02X}, received 0x{got:02X}"
        await wait_idle(dut)
        dut._log.info(f"0x{value:02X} OK")


@cocotb.test()
async def test_held_send_sends_once(dut):
    await reset(dut)
    dut.ui_in.value = 0x5A
    dut.uio_in.value = 1                    # hold SEND down
    got = await uart_receive(dut)
    assert got == 0x5A
    await wait_idle(dut)

    # SEND is still held: line must stay idle for two more frame times
    for _ in range(2 * FRAME_CLKS):
        await RisingEdge(dut.clk)
        assert tx(dut) == 1, "second frame sent while SEND held"
    dut.uio_in.value = 0
