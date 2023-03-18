from typing import List, Tuple, Optional

from amaranth import Signal
from amaranth.sim import Simulator, Delay, Settle

from ..config import SIM_CLOCK
from ..i2c import Speed
from .i2c_verifier import I2CVerifier
from .start_top import Top


class Bench:
    dut: Top
    iv: I2CVerifier

    def __init__(self, dut: Top):
        self.dut = dut
        self.iv = I2CVerifier(dut)

    def __call__(self):
        yield from self.bench_complete()
        yield from self.bench_nacks()

    def bench_complete(self, *, nack_after: Optional[int] = None):
        # Push the button.
        yield from self.iv.switch()

        # Enqueue the data.
        assert not (yield self.dut.i2c.i_stb)
        assert (yield self.dut.i2c.fifo.w_en)
        assert (yield self.dut.i2c.fifo.w_data) == 0xAF
        assert not (yield self.dut.i2c.fifo.r_rdy)
        assert (yield self.dut.i2c.fifo.r_level) == 0
        yield Delay(SIM_CLOCK)
        yield Settle()

        # Data is enqueued, we're strobing I2C.  I2C still high.
        assert (yield self.dut.i2c.i_stb)
        assert not (yield self.dut.i2c.fifo.w_en)
        assert (yield self.dut.i2c.fifo.r_rdy)
        assert (yield self.dut.i2c.fifo.r_level) == 1

        assert (yield self.dut.i2c._scl.o)
        assert (yield self.dut.i2c._sda.o)
        yield Delay(SIM_CLOCK)
        yield Settle()

        yield from self.iv.start()

        yield from self.iv.send((0x3C << 1) | 0)
        if nack_after == 1:
            yield from self.iv.nack()
        else:
            yield from self.iv.ack()
            yield from self.iv.send(0xAF, next=0x8C)
            if nack_after == 2:
                yield from self.iv.nack()
            else:
                yield from self.iv.ack()
                yield from self.iv.send(0x8C, next="STOP")
                if nack_after == 3:
                    yield from self.iv.nack()
                else:
                    yield from self.iv.ack()

        yield from self.iv.stop()

        for _ in range(3):
            yield Delay(SIM_CLOCK)
            yield Settle()
            assert (yield self.dut.i2c._scl.o)
            assert (yield self.dut.i2c._sda.o)

    def bench_nacks(self):
        yield from self.bench_complete(nack_after=1)
        yield from self.bench_complete(nack_after=2)
        yield from self.bench_complete(nack_after=3)


def prep_start(*, speed: Speed) -> Tuple[Top, Simulator, List[Signal]]:
    dut = Top(speed=speed)

    sim = Simulator(dut)
    sim.add_clock(SIM_CLOCK)
    sim.add_sync_process(Bench(dut).__call__)

    return (
        dut,
        sim,
        [
            dut.button.o_up,
            dut.i2c.i_addr,
            dut.i2c.i_rw,
            dut.i2c.i_stb,
            dut.i2c.fifo.w_rdy,
            dut.i2c.fifo.w_en,
            dut.i2c.fifo.w_data,
            dut.i2c.fifo.w_level,
            dut.i2c.fifo.r_rdy,
            dut.i2c.fifo.r_en,
            dut.i2c.fifo.r_data,
            dut.i2c.fifo.r_level,
            dut.i2c.o_busy,
            dut.i2c.o_ack,
            dut.i2c._byte,
            dut.i2c._byte_ix,
            dut.i2c._scl_o,
            dut.i2c._sda_oe,
            dut.i2c._sda_o,
            dut.i2c._sda_i,
        ],
    )


__all__ = ["prep_start"]
