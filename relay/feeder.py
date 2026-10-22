from dataclasses import dataclass, field
import numpy as np


@dataclass
class Feeder:
    kv: float
    source_mva_max: float
    source_mva_min: float
    source_xr: float
    tx_mva: float
    tx_z_pct: float
    tx_xr: float
    buses: list
    sections: list
    loads_mva: list
    relays: list = field(default_factory=list)

    def _z_source(self, mva):
        z = self.kv ** 2 / mva
        r = z / np.sqrt(1 + self.source_xr ** 2)
        return complex(r, r * self.source_xr)

    def _z_tx(self):
        z = self.tx_z_pct / 100 * self.kv ** 2 / self.tx_mva
        r = z / np.sqrt(1 + self.tx_xr ** 2)
        return complex(r, r * self.tx_xr)

    def z_to_bus(self, i, case="max"):
        z = self._z_source(self.source_mva_max if case == "max" else self.source_mva_min) + self._z_tx()
        for L, r, x in self.sections[:i]:
            z += L * complex(r, x)
        return z

    def fault_3ph(self, i, case="max", c=1.1):
        return c * self.kv * 1e3 / np.sqrt(3) / abs(self.z_to_bus(i, case))

    def fault_2ph_min(self, i):
        return np.sqrt(3) / 2 * self.fault_3ph(i, "min", c=1.0)

    def load_downstream(self, i):
        mva = sum(self.loads_mva[i + 1:])
        return mva * 1e3 / (np.sqrt(3) * self.kv)

    def tx_rated_current(self):
        return self.tx_mva * 1e3 / (np.sqrt(3) * self.kv)


def default_feeder():
    f = Feeder(
        kv=11.0,
        source_mva_max=500.0, source_mva_min=250.0, source_xr=10.0,
        tx_mva=20.0, tx_z_pct=10.0, tx_xr=15.0,
        buses=["SS 11 kV bus", "Section A", "Section B", "Section C"],
        sections=[(4.0, 0.273, 0.363), (5.0, 0.273, 0.363), (6.0, 0.273, 0.363)],
        loads_mva=[0.0, 3.0, 2.5, 2.0],
    )
    f.relays = [
        ("Incomer (transformer LV)", 0, f.tx_rated_current(), 1.25),
        ("Feeder breaker", 0, f.load_downstream(0), 1.5),
        ("Recloser A", 1, f.load_downstream(1), 1.5),
        ("Recloser B", 2, f.load_downstream(2), 1.5),
    ]
    return f
