#!/usr/bin/env python

import importlib.util
import re
import sys
import subprocess
from argparse import ArgumentParser
from pathlib import Path

from amaranth.back import rtlil
from amaranth.hdl import Fragment
from amaranth_boards.icebreaker import ICEBreakerPlatform

from sim import BENCHES
from i2c import Speed
from formal import formal as prep_formal
from oled import Top


def _outfile(dir, ext):
    base = Path(sys.argv[0])
    return str(base.parent / dir / f"oled_i2c{ext}")


def sim(args):
    _, sim, traces = BENCHES[args.bench](speed=Speed(args.speed))

    gtkw_file = _outfile("build", ".gtkw") if args.gtkw else None
    sim_exc = None
    with sim.write_vcd(_outfile("build", ".vcd"), gtkw_file=gtkw_file, traces=traces):
        try:
            sim.run()
        except AssertionError as exc:
            sim_exc = exc

    if gtkw_file:
        if sys.platform == "darwin":
            cmd = f"open {gtkw_file}"
        else:
            cmd = gtkw_file
        subprocess.run(cmd, shell=True)

    if sim_exc:
        raise sim_exc


def formal(_):
    design, ports = prep_formal()
    fragment = Fragment.get(design, None)
    output = rtlil.convert(fragment, name="formal_top", ports=ports)
    with open(_outfile("build", ".il"), "w") as f:
        f.write(output)

    sby_file = _outfile("formal", ".sby")
    subprocess.run(f"sby --prefix build/oled_i2c -f {sby_file}", shell=True)


def _print_file_between(path, start, end, *, prefix=None):
    with open(path, "r") as f:
        for line in f:
            if start.match(line):
                break
        else:
            return

        for line in f:
            if end.match(line):
                return
            line = line.rstrip()
            if prefix is not None:
                line = line.removeprefix(prefix)
            print(line)


def build(args):
    ICEBreakerPlatform().build(
        Top(speed=Speed(args.speed)),
        do_program=args.program,
        debug_verilog=args.verilog,
    )

    heading = re.compile(r"^\d+\.\d+\. Printing statistics\.$", flags=re.MULTILINE)
    next_heading = re.compile(r"^\d+\.\d+\. ", flags=re.MULTILINE)
    _print_file_between("build/top.rpt", heading, next_heading)

    print("Device utilisation:")
    heading = re.compile(r"^Info: Device utilisation:$", flags=re.MULTILINE)
    next_heading = re.compile(r"^Info: Placed ", flags=re.MULTILINE)
    _print_file_between("build/top.tim", heading, next_heading, prefix="Info: ")


def vsh(args):
    from vsh import run

    run(args)


def main():
    parser = ArgumentParser(prog="fpgaxp.oled.main")
    subparsers = parser.add_subparsers(required=True)

    sim_parser = subparsers.add_parser(
        "sim",
        help="simulate the design",
    )
    sim_parser.set_defaults(func=sim)
    sim_parser.add_argument(
        "bench",
        choices=BENCHES.keys(),
        help="which bench to run",
    )
    sim_parser.add_argument(
        "-s",
        "--speed",
        choices=[str(s) for s in Speed.VALID_SPEEDS],
        help="bus speed to sim at",
        default=str(Speed.VALID_SPEEDS[0]),
    )
    sim_parser.add_argument(
        "-G",
        "--no-gtkw",
        action="store_false",
        dest="gtkw",
        help="don't write and open a GTKWave file on completion",
    )

    formal_parser = subparsers.add_parser(
        "formal",
        help="formally verify the design",
    )
    formal_parser.set_defaults(func=formal)

    build_parser = subparsers.add_parser(
        "build",
        help="build the design, and optionally program it",
    )
    build_parser.set_defaults(func=build)
    build_parser.add_argument(
        "-s",
        "--speed",
        choices=[str(s) for s in Speed.VALID_SPEEDS],
        help="bus speed to build at",
        default=str(Speed.VALID_SPEEDS[0]),
    )
    build_parser.add_argument(
        "-p",
        "--program",
        action="store_true",
        help="program the design onto the iCEBreaker",
    )
    build_parser.add_argument(
        "-v",
        "--verilog",
        action="store_true",
        help="output debug Verilog",
    )

    if importlib.util.find_spec("pyglet") is not None:
        vsh_parser = subparsers.add_parser(
            "vsh",
            help="run the Virtual SH1107",
        )
        vsh_parser.set_defaults(func=vsh)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
