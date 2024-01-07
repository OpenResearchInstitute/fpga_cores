#!/usr/bin/env python3
#
# FPGA core library
#
# Copyright 2016-2022 by Andre Souto (suoto)
#
# This source describes Open Hardware and is licensed under the CERN-OHL-W v2
#
# You may redistribute and modify this documentation and make products using it
# under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).This
# documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
# INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
# PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.
#
# Source location: https://github.com/suoto/fpga_cores
#
# As per CERN-OHL-W v2 section 4.1, should You produce hardware based on these
# sources, You must maintain the Source Location visible on the external case
# of the FPGA Cores or other product you make using this documentation.

"HDL Library test runner"

# pylint: disable=missing-docstring

import os.path as p
import random
import re
import struct

from vunit.ui import VUnit  # type: ignore
from vunit.vunit_cli import VUnitCLI  # type: ignore

ROOT = p.abspath(p.dirname(__file__))


class GhdlPragmaHandler:  # pylint: disable=too-few-public-methods
    """
    Removes code between arbitraty pragmas
    -- ghdl translate_off
    this is ignored
    -- ghdl translate_on
    """

    _PRAGMA = re.compile(
        r"\s*--\s*ghdl\s+translate_off[\r\n].*?[\n\r]\s*--\s*ghdl\s+translate_on",
        flags=re.DOTALL | re.I | re.MULTILINE,
    )

    def run(self, code, file_name):  # pylint: disable=unused-argument,no-self-use
        for word in ("ghdl", "translate_on", "translate_off"):
            if word not in code:
                return code

        result = self._PRAGMA.sub(r"", code)

        return result


def main():
    cli = VUnitCLI()
    cli.parser.add_argument(
        "--seed",
        action="store",
        help="Random seed for the tests",
        type=int,
        default=random.randint(-1 << 31, 1 << 31),  # VHDL integer range
    )

    args = cli.parse_args()

    print(f"Seed: {args.seed}")

    cli = VUnit.from_args(args=args)

    cli.add_osvvm()
    cli.enable_location_preprocessing()
    cli.add_com()
    if cli.get_simulator_name() == "ghdl":
        cli.add_preprocessor(GhdlPragmaHandler())

    cli.add_library("fpga_cores").add_source_files(p.join(ROOT, "src", "*.vhd"))

    cli.add_library("str_format").add_source_files(
        p.join(ROOT, "dependencies", "hdl_string_format", "src", "*.vhd")
    )

    cli.add_library("tb")
    cli.library("tb").add_source_files(p.join(ROOT, "testbench", "*.vhd"))

    cli.add_library("fpga_cores_sim")
    cli.library("fpga_cores_sim").add_source_files(p.join(ROOT, "sim", "*.vhd"))

    cli.add_library("exp_golomb").add_source_files(
        p.join(ROOT, "src", "exponential_golomb", "*.vhd")
    )

    addTests(cli, args.seed)

    cli.set_compile_option("modelsim.vcom_flags", ["-explicit"])

    # Not all options are supported by all GHDL backends
    #  cli.set_compile_option("ghdl.a_flags", ["-frelaxed-rules"])
    #  cli.set_compile_option("ghdl.a_flags", ["-frelaxed-rules", "-O0", "-g"])
    cli.set_compile_option("ghdl.a_flags", ["-frelaxed-rules", "-O2", "-g"])

    # Make components not bound (error 3473) an error
    cli.set_sim_option("modelsim.vsim_flags", ["-error", "3473", '-voptargs="+acc=n"'])
    #  cli.set_sim_option("ghdl.sim_flags", ["-frelaxed-rules"])
    #  cli.set_sim_option("ghdl.elab_e", ["-frelaxed-rules"])
    cli.set_sim_option("ghdl.elab_flags", ["-frelaxed-rules"])

    cli.set_sim_option("disable_ieee_warnings", True)
    cli.set_sim_option("modelsim.init_file.gui", p.join(ROOT, "wave.do"))
    cli.main()


def addTests(cli, seed):
    addAsyncFifoTests(cli.library("tb").entity("async_fifo_tb"), seed)
    addAxiStreamDelayTests(cli.library("tb").entity("axi_stream_delay_tb"), seed)
    addAxiFileReaderTests(cli.library("tb").entity("axi_file_reader_tb"), seed)
    addAxiFileCompareTests(cli.library("tb").entity("axi_file_compare_tb"), seed)
    addAxiWidthConverterTests(
        cli.library("tb").entity("axi_stream_width_converter_tb"), seed
    )
    addAxiEmbiggenerTests(cli.library("tb").entity("axi_embiggener_tb"), seed)
    addAxiArbiterTests(cli.library("tb").entity("axi_stream_arbiter_tb"), seed)

    # Add seed to other testbenches
    for entity in (
        cli.library("tb").entity("axi_stream_frame_slicer_tb"),
        cli.library("tb").entity("axi_stream_frame_padder_tb"),
        cli.library("tb").entity("axi_stream_frame_fifo_tb"),
        cli.library("tb").entity("axi_stream_replicate_tb"),
    ):
        entity.add_config(name="with_seed", generics=dict(seed=seed))


def addAsyncFifoTests(entity, seed):
    clk_period_list = (4, 11)

    for wr_clk_period in clk_period_list:
        for rd_clk_period in clk_period_list:
            for wr_rand, rd_rand in (
                (0, 0),
                (3, 0),
                (0, 3),
                (5, 5),
            ):
                name = ",".join(
                    [
                        f"wr_clk_period={wr_clk_period}",
                        f"rd_clk_period={rd_clk_period}",
                        f"wr_rand={wr_rand}",
                        f"rd_rand={rd_rand}",
                    ]
                )

                entity.add_config(
                    name=name,
                    generics=dict(
                        WR_CLK_PERIOD_NS=wr_clk_period,
                        RD_CLK_PERIOD_NS=rd_clk_period,
                        WR_EN_RANDOM=wr_rand,
                        RD_EN_RANDOM=rd_rand,
                        SEED=seed,
                    ),
                )


def addAxiStreamDelayTests(entity, seed):
    "Parametrizes the delays for the AXI stream delay test"
    for delay in (1, 2, 8):
        entity.add_config(
            name=f"delay={delay}", generics=dict(DELAY_CYCLES=delay, SEED=seed)
        )


def addAxiFileCompareTests(entity, seed):
    "Parametrizes the AXI file compare testbench"
    test_file = p.join(ROOT, "vunit_out", "file_compare_input.bin")
    reference_file = p.join(ROOT, "vunit_out", "file_compare_reference_ok.bin")

    if not (p.exists(test_file) and p.exists(reference_file)):
        generateAxiFileReaderTestFile(
            test_file=test_file,
            reference_file=reference_file,
            data_width=32,
            length=32 * 8,
        )

    tdata_single_error_file = p.join(
        ROOT, "vunit_out", "file_compare_reference_tdata_1_error.bin"
    )
    tdata_two_errors_file = p.join(
        ROOT, "vunit_out", "file_compare_reference_tdata_2_errors.bin"
    )
    tlast_error_file = p.join(
        ROOT, "vunit_out", "file_compare_reference_tlast_error.bin"
    )

    if not p.exists(tdata_single_error_file):
        with open(reference_file, "rb") as fd:
            ref_data = fd.read().split(b"\n")

        with open(tdata_single_error_file, "wb") as fd:
            # Skip one, duplicate another so the size is the same
            data = (
                ref_data[:7]
                + [
                    ref_data[8],
                ]
                + ref_data[8:]
            )
            fd.write(b"\n".join(data))

    if not p.exists(tdata_two_errors_file):
        with open(reference_file, "rb") as fd:
            ref_data = fd.read().split(b"\n")

        with open(tdata_two_errors_file, "wb") as fd:
            # Skip one, duplicate another so the size is the same
            data = (
                ref_data[:7]
                + [ref_data[8], ref_data[8]]
                + ref_data[9:16]
                + [
                    ref_data[17],
                ]
                + ref_data[17:]
            )
            fd.write(b"\n".join(data))

    if not p.exists(tlast_error_file):
        with open(reference_file, "rb") as fd:
            ref_data = fd.read().strip().split(b"\n")

        with open(tlast_error_file, "wb") as fd:
            # Format is "tdata,tkeep,tlast", change tlast to 0
            last_entry = ref_data[-1].split(b",")
            data = ref_data[:-1] + [b",".join([last_entry[0], b"0", b"0"])]
            fd.write(b"\n".join(data))

    entity.add_config(
        name="all",
        generics=dict(
            input_file=test_file,
            reference_file=reference_file,
            tdata_single_error_file=tdata_single_error_file,
            tdata_two_errors_file=tdata_two_errors_file,
            tlast_error_file=tlast_error_file,
            seed=seed,
        ),
    )


def addAxiFileReaderTests(entity, seed):
    "Parametrizes the AXI file reader testbench"
    # Dict with data_width: {lengths in bytes}
    configs = {
        1: [1, 2],
        8: [1, 8, 16, 24],
        16: [1, 2, 3, 4, 8, 9],
        64: [16, 17, 18, 19],
    }

    for data_width, length_list in configs.items():
        all_configs = []

        for length in length_list:
            basename = f"file_reader_data_width_{data_width}_length_{length}_bytes"

            test_file = p.join(ROOT, "vunit_out", basename + "_input.bin")
            reference_file = p.join(ROOT, "vunit_out", basename + "_reference.bin")

            if not (p.exists(test_file) and p.exists(reference_file)) or (
                p.getmtime(__file__)
                > max(p.getmtime(test_file), p.getmtime(reference_file))
            ):
                generateAxiFileReaderTestFile(
                    test_file=test_file,
                    reference_file=reference_file,
                    data_width=data_width,
                    length=length,
                )

            test_cfg = ",".join([test_file, reference_file])

            all_configs += [test_cfg]

        entity.add_config(
            name=f"multiple,data_width={data_width}",
            generics=dict(
                DATA_WIDTH=data_width, test_cfg="|".join(all_configs), seed=seed
            ),
        )


def swapBits(value, width=8):
    "Swaps LSB and MSB bits of <value>, considering its width is <width>"
    v_in_binary = bin(value)[2:]

    assert len(v_in_binary) <= width, "input is too big"

    v_in_binary = "0" * (width - len(v_in_binary)) + v_in_binary
    return int(v_in_binary[::-1], 2)


def generateAxiFileReaderTestFile(test_file, reference_file, data_width, length):
    "Create a pair of test files for the AXI file reader testbench"
    print("Generating AXI file reader test files")
    print("- test_file:      ", test_file)
    print("- reference_file: ", reference_file)
    print("- data_width:     ", data_width, "bits")
    print("- length:         ", length, "bytes")

    test_data = tuple(random.randint(0, 255) for _ in range(length))

    print("- test_data:      ", test_data)

    with open(test_file, "wb") as fd:
        fd.write(struct.pack("<" + length * "B", *test_data))

    # Format will depend on the data width, need to be wide enough for to fit
    # one character per nibble
    lines = []
    tkeep_fmt = f"%.{data_width//8//4}x"

    if data_width >= 8:
        line = []
        tkeep = 0
        for i, byte in enumerate(test_data):
            line.insert(0, f"{byte:02x}")
            tlast = i == length - 1
            if (8 * (i + 1) % data_width) == 0:
                if tlast:
                    tkeep = (1 << len(line)) - 1
                lines += [
                    ",".join(["".join(line), tkeep_fmt % tkeep, "1" if tlast else "0"])
                ]
                line = []
        if line:
            tkeep = (1 << len(line)) - 1
            line = (data_width // 8 - len(line)) * ["00"] + line
            lines += [",".join(["".join(line), tkeep_fmt % tkeep, "1"])]
    else:
        # Flatten the test data into a bit string and slice it with data_width
        for i, byte in enumerate(test_data):
            print(i, hex(byte))
        flattened_bin_data = ""
        for byte in test_data:
            # Convert integer into binary with the LSB to the left so index 0
            # of the flattened array is index 0 of the first word
            little_endian_word = "".join(reversed(bin(byte)[2:]))
            # Adjust result of 'bin' to 8 bits width and append it to the flattened
            # buffer
            flattened_bin_data += little_endian_word + "0" * (
                8 - len(little_endian_word)
            )

        print(flattened_bin_data, len(flattened_bin_data))
        assert len(flattened_bin_data) % 8 == 0

        lines = []
        while flattened_bin_data:
            word = int(flattened_bin_data[:data_width], 2)
            flattened_bin_data = flattened_bin_data[data_width:]

            tlast = not flattened_bin_data
            lines += [",".join([f"{word:x}", "", "1" if tlast else "0"])]

    with open(reference_file, "w") as fd:
        fd.write("\n".join(lines))
        fd.write("\n")


def addAxiWidthConverterTests(entity, seed):
    # Only add equal widths once
    entity.add_config(
        name="same_widths",
        generics=dict(
            INPUT_DATA_WIDTH=32,
            OUTPUT_DATA_WIDTH=32,
            seed=seed,
        ),
    )

    for input_data_width in {1, 8, 24, 32, 128}:
        for output_data_width in {1, 3, 8, 24, 32, 128} - {input_data_width}:
            if output_data_width >= input_data_width:
                continue
            entity.add_config(
                name=f"input_data_width={input_data_width},"
                + f"output_data_width={output_data_width}",
                generics=dict(
                    INPUT_DATA_WIDTH=input_data_width,
                    OUTPUT_DATA_WIDTH=output_data_width,
                    seed=seed,
                ),
            )


def addAxiEmbiggenerTests(entity, seed):
    # following example from addAxiWidthConverterTests, but only one case applies
    input_data_width = 32
    output_data_width = 128
    entity.add_config(
        name=f"input_data_width={input_data_width},"
        + f"output_data_width={output_data_width}",
        generics=dict(
            INPUT_DATA_WIDTH=input_data_width,
            OUTPUT_DATA_WIDTH=output_data_width,
            seed=seed,
        ),
    )


def addAxiArbiterTests(entity, seed):
    for test in entity.get_tests():
        for register_inputs in (True, False):
            if test.name.startswith("test_round_robin"):
                test.add_config(
                    name=f"mode=ROUND_ROBIN,register_inputs={register_inputs}",
                    generics=dict(
                        MODE="ROUND_ROBIN", REGISTER_INPUTS=register_inputs, seed=seed
                    ),
                )
            if test.name.startswith("test_interleaved"):
                test.add_config(
                    name=f"mode=INTERLEAVED,register_inputs={register_inputs}",
                    generics=dict(
                        MODE="INTERLEAVED", REGISTER_INPUTS=register_inputs, seed=seed
                    ),
                )
            if test.name.startswith("test_absolute"):
                test.add_config(
                    name=f"mode=ABSOLUTE,register_inputs={register_inputs}",
                    generics=dict(
                        MODE="ABSOLUTE", REGISTER_INPUTS=register_inputs, seed=seed
                    ),
                )


if __name__ == "__main__":
    import sys

    sys.exit(main())
