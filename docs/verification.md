# Verification

This document describes how the design is verified and what bugs verification caught.
It covers milestone 1 (fixed-function UART TX) and will grow as the programmable core
is added.

## Approach

| Level | Tool | What it checks |
|---|---|---|
| RTL simulation | cocotb + Icarus Verilog | Functional behaviour of the SystemVerilog source |
| Gate-level simulation | cocotb + Icarus Verilog, run on the post-place-and-route netlist from the Tiny Tapeout GDS flow | That the synthesized, placed and routed design behaves the same as the RTL |
| Signoff | Tiny Tapeout precheck (DRC, LVS, timing) | That the layout is manufacturable and meets timing |

The same cocotb testbench (`test/test.py`) runs against both the RTL and the gate-level
netlist, so any difference between the two is a bug in the design or the flow, not in
the test.

## Testbench

The testbench drives a 50 MHz clock and decodes the TX pin with a software UART
receiver (`uart_receive`) that waits for the falling edge of the start bit, then
samples each bit in the middle of its 434-cycle period. It checks that the start bit
is still low at mid-bit and that the stop bit is high.

| Test | What it checks |
|---|---|
| `test_idle_after_reset` | After reset, TX idles high and BUSY is low. |
| `test_send_bytes` | 15 bytes are sent and received correctly: the edge cases `0x41`, `0x00`, `0xFF`, `0x55`, `0xAA` (all-zero, all-one and alternating bit patterns), plus 10 random bytes. Each byte waits for BUSY to fall before the next one. |
| `test_held_send_sends_once` | Holding SEND high sends exactly one byte: after the first frame, TX stays idle for two more frame times. This checks the synchronizer and rising-edge detector on SEND. |

## Bug found by gate-level simulation: X-propagation with synchronous reset

**Symptom.** All three tests passed in RTL simulation. In gate-level simulation,
`test_idle_after_reset` passed, but `test_send_bytes` and `test_held_send_sends_once`
failed with:

```
ValueError: Can't convert LogicArray to int: it contains non-0/1 values
```

This meant the TX or BUSY output was `X` (unknown) when the testbench sampled it.

**Finding the flop.** Scanning the waveform from the failing run (`tb.fst`) for `X`
values on every register showed that all registers took a known value on the first
clock edge of reset (20 ns) except one: `u_tx.bit_cnt[2]` was `X` from time 0 and
never became 0 or 1, even while `rst_n` was held low. That `X` stayed hidden until it
spread into `bit_cnt[3]` at 35.4 µs, and then into `baud_cnt`, `shreg` and `tx` at
52.8 µs, which is where `test_send_bytes` failed.

**Cause: X-pessimism in the synthesized reset logic.** The original design used a
synchronous reset (`if (rst)` inside `always_ff @(posedge clk)`). The IHP cell library's
flop (`sg13cmos5l_dfrbpq_1`) has an asynchronous reset pin, but for a synchronous reset
Yosys ties that pin inactive (to a tie-high cell) and builds the reset into the logic
in front of D. For `bit_cnt[2]` that logic came out as:

```
D = ~( (~bit_cnt[2] & _037_) | (~_033_ & bit_cnt[2] & _040_) )
```

This is a 2-way choice selected by the flop's own output. In real silicon the flop
powers up as 0 or 1, both branches evaluate to 0 during reset, and the flop resets
correctly. In simulation the flop starts as `X`, both AND terms contain `X`, so D is `X`,
and the flop loads `X` again on every clock edge. The simulator cannot see that both
branches agree, so reset never clears the `X`. The RTL simulation did not show this,
because there the reset assignment `bit_cnt <= '0` runs directly.

**Fix.** Commit `e2f9f46` switched every flop to an active-low asynchronous reset
(`always_ff @(posedge clk or negedge rst_n)`). Reset now drives each flop's `RESET_B`
pin directly, so it does not depend on the logic in front of D, and every register is
in a known state as soon as `rst_n` goes low.

**Result.** After `e2f9f46`, all 3 tests pass in both RTL and gate-level simulation
(previously 1/3 at gate level). CI run:
<https://github.com/rohtakpat314/JSC-asic-protocol-2027/actions/runs/44571247731>
(GitHub keeps run logs for a limited time; the tests can be re-run from `test/`.)

**Lesson.** RTL simulation alone was not enough: the RTL was correct, and the problem
only showed up in the synthesized netlist. This particular failure was a simulation
artifact (the silicon would most likely have reset correctly), but an `X` that survives
reset can't be told apart from a real bug without this kind of netlist analysis, and
the async reset removes the question entirely. Gate-level simulation is now a required
check for every change.

## Known limitations and next steps

- **Reset deassertion is not synchronized.** `rst_n` is asserted asynchronously (good),
  but it is also released asynchronously. If it is released close to a clock edge,
  flops can come out of reset on different cycles. A two-flop reset synchronizer will
  be added.
- The testbench only covers the fixed UART. Once the programmable core exists, tests will
  run assembled firmware on the core and check the protocol waveforms.
- Planned: constrained-random tests and formal checks (for example, with SymbiYosys)
  on the core's instruction decoder and the program loader.
