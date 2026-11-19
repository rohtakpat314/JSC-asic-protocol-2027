## How it works

Milestone 1 of a programmable protocol emulator: a fixed-function UART transmitter
that sends one byte over 115200 baud 8N1.

- An 8-bit byte is read from the dedicated inputs `ui[7:0]`.
- A rising edge on `uio[0]` (SEND) starts transmission. SEND is synchronized with a
  2-flop synchronizer and edge-detected, so holding it high sends exactly one byte.
- The transmitter shifts out a start bit (0), 8 data bits LSB-first, and a stop bit (1),
  each lasting 434 clock cycles (50 MHz / 115200 baud).
- `uo[1]` (BUSY) is high while a frame is being sent; new SEND edges are ignored until
  it falls.
- The TX line idles high after reset.

Later milestones replace the fixed UART with a small programmable core that can
bit-bang UART, SPI, I2C, and other protocols from firmware.

## How to test

1. Set the clock to 50 MHz and apply reset (`rst_n` low, then high).
2. Set the byte to send on `ui[7:0]` and hold it steady.
3. Pulse `uio[0]` (SEND) high, then low.
4. Read the byte at 115200 baud, 8N1, on `uo[0]` (UART_TX) with any USB-UART adapter
   or the RP2350 on the demo board. Wait for `uo[1]` (BUSY) to go low before sending
   the next byte.

Example: `ui = 0x41` followed by a SEND pulse transmits the character "A".

## External hardware

None required. Any 3.3 V USB-UART adapter (or the demo board's RP2350) can receive
the output on `uo[0]`.
