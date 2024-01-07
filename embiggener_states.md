# State Diagram for Embiggener

This VHDL entity translates a 32-bit-wide AXI-S interface (DMA) to the 128-bit-wide interface (similar to AXI-S) expected by the DAC FIFO in the Analog Devices ADRV9371-ZC706 reference design.

```mermaid
stateDiagram-v2
state "InReset:\nRST signal holding us in reset\ns_tready = 0\nm_tvalid =" as inreset
state "Empty:\nNo input data in the output register\ns_tready = 1\nm_tvalid = 0" as empty
state "Have0:\nOne word in the output register, awaiting second word\ns_tready = 1\nm_tvalid = 0" as have0
state "Have1:\nTwo words in the output register, awaiting third word\ns_tready = 1\nm_tvalid = 0" as have1
state "Have2:\nThree words in the output register, awaiting fourth word\ns_tready = 1\nm_tvalid = 0" as have2
state "Have3:\nOutput register full, maybe awaiting consumer\ns_tready = m_tready\nm_tvalid = 1" as have3

[*] --> inreset
inreset --> empty: on clk if RST low
empty --> have0: on clk if s_tvalid high\nload buffer[31..0]
have0 --> have1: on clk if s_tvalid high\nload buffer[63..32]
have1 --> have2: on clk if s_tvalid high\nload buffer[95..64]
have2 --> have3: on clk if s_tvalid high\nload buffer[127..96]
have3 --> have0: on clk if m_tready high\nload buffer[31..0]

```

