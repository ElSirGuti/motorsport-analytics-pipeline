"""iRacing OnPitRoad se mapea al canal canonico InPit (deteccion de vueltas de boxes)."""
import numpy as np

from src.io.native_common import RawChannel, pick_channels, DISCRETE


def _ch(name, vals):
    arr = np.asarray(vals, dtype=np.float64)
    return RawChannel(name=name, unit="", freq=60.0, n=len(arr), reader=lambda a=arr: a, discrete=True)


def test_onpitroad_maps_to_inpit():
    chosen = pick_channels({"OnPitRoad": [_ch("OnPitRoad", [1, 1, 0, 0])]})
    assert "InPit" in chosen
    assert chosen["InPit"].name == "OnPitRoad"
    assert "InPit" in DISCRETE
