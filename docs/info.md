<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project implements a **pipeline skid buffer**, a one-deep elastic pipeline stage with 8-bit data and ready/valid handshaking. It allows two pipeline stages running at different speeds to communicate without losing data or stalling unnecessarily.

The handshaking protocol uses two control signals: `valid` indicates that the sender has data to send, and `ready` indicates that the receiver can accept data. A transfer only happens when both are high at the same time.

The buffer has two key behavioral rules:

- `ready_o` is combinational: `ready_o = ready_i | ~valid_o`. The buffer can accept new data if it is currently empty, or if the downstream is accepting data this same cycle.
- `valid_o` is registered: it reflects whether the internal data register holds valid data. Once asserted, it will not drop until a transfer completes.

This allows the buffer to sustain full throughput with no wasted cycles when both sides are active.

Two compile-time parameters control datapath behavior:

- `datapath_gate_p` (set to 1): the data register only updates when a valid handshake occurs, which reduces unnecessary switching and saves power.
- `datapath_reset_p` (set to 0): the data register is not cleared on reset. Only `valid_o` resets to 0. This saves area by removing the reset path from the data register.

### Pin mapping

|      Pin      | Direction |                  Signal                     |
|---------------|-----------|---------------------------------------------|
| `ui_in[7:0]`  |   Input   | `data_i`: 8-bit upstream data               |
| `uio_in[1]`   |   Input   | `valid_i`: upstream data valid              |
| `uio_in[0]`   |   Input   | `ready_i`: downstream ready to accept       |
| `uo_out[7:0]` |   Output  | `data_o`: 8-bit downstream data             |
| `uio_out[3]`  |   Output  | `valid_o`: downstream data valid            |
| `uio_out[2]`  |   Output  | `ready_o`: backpressure signal to upstream  |

## How to test

Drive the input pins from a producer and observe the output pins each clock cycle.

**Basic transfer:** Set `valid_i` and `ready_i` both high with data on `ui_in`. One cycle later, `valid_o` will go high and `data_o` will hold the transferred value.

**Backpressure:** Set `valid_i` high while holding `ready_i` low. The buffer captures the data and pulls `ready_o` low to stall the upstream. `valid_o` stays high and `data_o` holds steady until `ready_i` goes high.

**Reset:** Pull `rst_n` low for at least one cycle. After release, `valid_o` must be 0 and `ready_o` must be 1 regardless of what state the buffer was in before.

The cocotb testbench covers reset state, reset while full, single transfer, back-to-back transfers at full throughput, backpressure with single and multi-cycle stalls, and 100 cycles of random stimulus verified against a Python reference model.

## GenAI tool usage

GenAI was used to generate the cocotb testbench and Python reference model. I specified the test scenarios including reset behavior, all ready/valid input combinations, single and extended stall and release sequences, and random stress testing, then reviewed the generated output for correctness against the RTL.

## External hardware

None.