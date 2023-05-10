import unittest
from typing import Final, Optional

from amaranth import Signal
from amaranth.sim import Delay, Settle

import sim
from common import Hz
from .i2c import I2C
from .test_i2c_top import TestI2CTop
from .virtual_i2c import VirtualI2C


# TODO: further unify with TestI2CRepeatedStart
class TestI2C(sim.TestCase):
    switch: Signal
    iv: VirtualI2C
    i2c: I2C

    @sim.always_args([(0x3C << 1) | I2C.RW.W, 0xAF, 0x8C])
    @sim.args(speed=Hz(100_000))
    @sim.args(speed=Hz(400_000))
    @sim.args(speed=Hz(1_000_000))
    @sim.args(speed=Hz(2_000_000))
    def test_sim_i2c(self, dut: TestI2CTop) -> sim.Generator:
        self.switch = dut.switch
        self.iv = VirtualI2C(dut.i2c)
        self.i2c = dut.i2c

        yield from self._bench_complete()
        yield from self._bench_nacks()

    def _bench_complete(self, *, nack_after: Optional[int] = None) -> sim.Generator:
        # Force the button push, we don't need to test it here.
        yield self.switch.eq(1)
        yield Delay(sim.clock())
        yield Settle()
        yield self.switch.eq(0)

        # Enqueue the data.
        assert not (yield self.i2c.i_stb)
        assert (yield self.i2c.fifo.w_en)
        assert (yield self.i2c.fifo.w_data) == 0x78
        assert not (yield self.i2c.fifo.r_rdy)
        yield Delay(sim.clock())
        yield Settle()

        # Data is enqueued, we're strobing I2C.  Lines still high.
        assert (yield self.i2c.i_stb)
        assert not (yield self.i2c.fifo.w_en)
        assert (yield self.i2c.fifo.r_rdy)
        assert (yield self.i2c.fifo.r_level) == 1

        assert (yield self.i2c.scl_o)
        assert (yield self.i2c.sda_o)
        yield Delay(sim.clock())
        yield Settle()

        yield from self.iv.start()

        yield from self.iv.send(0x78)
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
            yield Delay(sim.clock())
            yield Settle()
            assert (yield self.i2c.scl_o)
            assert (yield self.i2c.sda_o)

        assert not (yield self.i2c.fifo.r_rdy)
        assert not (yield self.i2c.o_busy)

    def _bench_nacks(self) -> sim.Generator:
        yield from self._bench_complete(nack_after=1)
        yield from self._bench_complete(nack_after=2)
        yield from self._bench_complete(nack_after=3)


if __name__ == "__main__":
    unittest.main()
