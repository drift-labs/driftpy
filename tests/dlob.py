from driftpy.dlob.dlob import DLOB
from dlob_test_constants import mock_perp_markets, mock_spot_markets
from driftpy.types import MarketType

def test_fresh_dlob_is_empty():
    dlob = DLOB()
    print("hello")
