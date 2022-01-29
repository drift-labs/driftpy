from driftpy.clearing_house import ClearingHouse


def test_local_idl():
    res = ClearingHouse.local_idl()
    assert res.name == "clearing_house"
