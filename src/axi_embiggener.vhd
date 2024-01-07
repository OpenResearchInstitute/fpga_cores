--
-- FPGA core library
--
-- Copyright 2014-2021 by Andre Souto (suoto)
-- Embiggened by Skunkwrx and Abraxas3d
--
-- This source describes Open Hardware and is licensed under the CERN-OHL-W v2
--
-- You may redistribute and modify this documentation and make products using it
-- under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).This
-- documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
-- INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
-- PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.
--
-- Source location: https://github.com/suoto/fpga_cores
--
-- As per CERN-OHL-W v2 section 4.1, should You produce hardware based on these
-- sources, You must maintain the Source Location visible on the external case
-- of the FPGA Cores or other product you make using this documentation.


---------------
-- Libraries --
---------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.common_pkg.all;
------------------------
-- Entity declaration --
------------------------
entity axi_embiggener is
  generic (
    INPUT_DATA_WIDTH    : natural := 32;
    OUTPUT_DATA_WIDTH   : natural := 128);
  port (
    -- Usual ports
    clk      : in  std_logic;
    rst      : in  std_logic;
    -- AXI stream input
    s_tready : out std_logic;
    s_tdata  : in  std_logic_vector(INPUT_DATA_WIDTH - 1 downto 0);
    s_tvalid : in  std_logic;
    s_tlast  : in  std_logic;
    -- AXI stream output
    m_tready : in  std_logic;
    m_tdata  : out std_logic_vector(OUTPUT_DATA_WIDTH - 1 downto 0);
    m_tvalid : out std_logic;
    -- There are other signals we do not know how to handle yet
    -- dma_xfer_req : out std_logic;
    m_tlast : out std_logic); -- encoder outputs this signal but we set it to 0
end axi_embiggener;

architecture axi_embiggener of axi_embiggener is

  ---------------
  -- Constants --
  ---------------
  constant INPUT_BYTE_WIDTH  : natural := (INPUT_DATA_WIDTH + 7) / 8;
  constant OUTPUT_BYTE_WIDTH : natural := (OUTPUT_DATA_WIDTH + 7) / 8;
  

  ------------------
  -- Sub programs --
  ------------------
  -- Sets the appropriate tkeep bits so that it representes the specified number of bytes,
  -- where bytes are in the LSB of tdata
  function get_tkeep ( constant valid_bytes : natural ) return std_logic_vector is
    variable result : std_logic_vector(OUTPUT_BYTE_WIDTH - 1 downto 0) := (others => '0');
  begin
    for i in 0 to result'length - 1 loop
      if i < valid_bytes then
        result(i) := '1';
      else
        result(i) := '0';
      end if;
    end loop;
    return result;
  end;

  -- function tkeep_to_byte_count ( constant tkeep : std_logic_vector ) return unsigned is
  --   variable candidate : std_logic_vector(tkeep'length - 1 downto 0) := (others => '0');
  -- begin
  --   candidate(0) := '1';

  --   for i in 0 to INPUT_BYTE_WIDTH - 1 loop
  --     if tkeep = candidate then
  --       -- (INPUT_BYTE_WIDTH - 1 downto i + 1 => '0') & (i downto 0 => '1') then
  --       return to_unsigned(i + 1, numbits(2*INPUT_BYTE_WIDTH));
  --     end if;

  --     candidate := candidate(tkeep'length - 2 downto 0) & '1';
  --   end loop;
  --   return (numbits(2*INPUT_BYTE_WIDTH) - 1 downto 0 => 'U');
  -- end function;

  function tkeep_to_byte_count ( constant tkeep : std_logic_vector ) return unsigned is
    variable result : unsigned(numbits(2*INPUT_BYTE_WIDTH) - 1 downto 0) := (others => '0');
  begin
    -- When tkeep is all ones we have INPUT_BYTE_WIDTH valid bytes
    if tkeep = (tkeep'range => '1') then
      result := result or to_unsigned(INPUT_BYTE_WIDTH, numbits(2*INPUT_BYTE_WIDTH));
    end if;
    -- Check for intermediate values
    for i in 0 to INPUT_BYTE_WIDTH - 2 loop
      if tkeep = (INPUT_BYTE_WIDTH - 1 downto i + 1 => '0') & (i downto 0 => '1') then
        result := result or to_unsigned(i + 1, numbits(2*INPUT_BYTE_WIDTH));
      end if;
    end loop;

    -- If result is all zeros we failed to convert, so return unknown instead
    if and(not result) then
      return (numbits(2*INPUT_BYTE_WIDTH) - 1 downto 0 => 'U');
    end if;
    return result;
  end function;

  -----------
  -- Types --
  -----------

  -------------
  -- Signals --
  -------------
  signal m_tdata_i    : std_logic_vector(OUTPUT_DATA_WIDTH - 1 downto 0);
  signal s_tready_i   : std_logic;
  signal m_tvalid_i   : std_logic;


  type state is (In_Reset, Empty, Have0, Have1, Have2, Have3);
  signal current_state, next_state : state; 
  signal big_buffer           : std_logic_vector(OUTPUT_DATA_WIDTH - 1 downto 0);



begin


  g_not_upsize : if INPUT_DATA_WIDTH >= OUTPUT_DATA_WIDTH or INPUT_DATA_WIDTH mod 8 /= 0 or OUTPUT_DATA_WIDTH mod INPUT_DATA_WIDTH /= 0 generate -- {{
    assert False
      report "Conversion from " & integer'image(INPUT_DATA_WIDTH) & " to " & integer'image(OUTPUT_DATA_WIDTH) & " is not currently supported"
      severity Failure;
  end generate g_not_upsize; -- }}


  g_upsize : if INPUT_DATA_WIDTH < OUTPUT_DATA_WIDTH generate -- {{
    -- AI abraxas3d to find out more about generate - thinking it's always with a test
    
   
  begin

    ---------------
    -- Processes --
    ---------------

    combinatorial:process(current_state, s_tvalid, m_tready) -- In_Reset, Empty, Load0, Have0, Load1, Have1, Load2, Have2, Load3, Have3

    begin
      next_state <= current_state; -- default value for next_state
      case current_state is
        when In_Reset =>
          s_tready_i <= '0';
          m_tvalid_i <= '0';
            next_state <= Empty;
        when Empty => 
          s_tready_i <= '1';
          m_tvalid_i <= '0';
          if s_tvalid = '1' then
            next_state <= Have0;
          end if;
        when Have0 =>
          s_tready_i <= '1';
          m_tvalid_i <= '0';
          if s_tvalid = '1' then
            next_state <= Have1;
          end if;
        when Have1 =>
          s_tready_i <= '1';
          m_tvalid_i <= '0';
          if s_tvalid = '1' then
            next_state <= Have2;
          end if;
        when Have2 =>
          s_tready_i <= '1';
          m_tvalid_i <= '0';
          if s_tvalid = '1' then
            next_state <= Have3;
          end if;
        when Have3 =>
          s_tready_i <= m_tready;
          m_tvalid_i <= '1';
          next_state <= Have0;
      end case;
    end process combinatorial;


    memory:process(rst, clk)  -- In_Reset, Empty, Have0, Have1, Have2, Have3
    begin
      if rising_edge(clk) then
        if rst = '1' then
          --s_tready_i <= '0';
          --m_tvalid_i <= '0';
          current_state <= In_Reset;
          --next_state <= Empty;
        else
          case current_state is
            when In_Reset =>
              current_state <= next_state;
            when Empty =>
              big_buffer(INPUT_DATA_WIDTH - 1 downto 0) <= s_tdata;
              current_state <= next_state;
            when Have0 =>
              big_buffer(2*INPUT_DATA_WIDTH - 1 downto INPUT_DATA_WIDTH) <= s_tdata;
              current_state <= next_state;
            when Have1 =>
              big_buffer(3*INPUT_DATA_WIDTH - 1 downto 2*INPUT_DATA_WIDTH) <= s_tdata;
              current_state <= next_state;
            when Have2 =>
              big_buffer(4*INPUT_DATA_WIDTH - 1 downto 3*INPUT_DATA_WIDTH) <= s_tdata;
              current_state <= next_state;
            when Have3 => 
              if m_tready = '1' then
                big_buffer(INPUT_DATA_WIDTH - 1 downto 0) <= s_tdata;
                current_state <= next_state;
              end if;
            when others =>
              NULL;
          end case;
        end if;
      end if;
    end process memory;


  end generate g_upsize; -- }}



  ------------------------------
  -- Asynchronous assignments --
  ------------------------------

  m_tdata      <= big_buffer when m_tvalid_i = '1' else (others => 'U');
  s_tready     <= s_tready_i;
  m_tvalid     <= m_tvalid_i;
  m_tlast      <= '0';


  -- ---------------
  -- -- Processes --
  -- ---------------
  -- -- First word flagging is common
  -- process(clk, rst)
  -- begin
  --   if rst = '1' then
  --     s_first_word <= '1';
  --   elsif rising_edge(clk) then

  --     if s_data_valid = '1' then
  --       s_first_word <= s_tlast;
  --     end if;

  --   end if;
  -- end process;

end axi_embiggener;

-- vim: set foldmethod=marker foldmarker=--\ {{,--\ }} :

