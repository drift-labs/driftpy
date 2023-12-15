import json
from construct import GreedyRange
from solders.pubkey import Pubkey
# from driftpy.types import Order
from anchorpy_core.idl import IdlField, IdlTypeDefined, Idl
from anchorpy.coder.idl import _field_layout

class DLOBOrder:
    def __init__(self, user: Pubkey, order):
        self.pubkey = user
        self.order = order

class DLOBOrders:
    def __init__(self, orders: list[DLOBOrder]):
        self.orders = orders

with open('dlob.json') as f:
    dlob_idl: Idl = json.load(f)

# This REALLY might not work
# I'm getting super nasty circular import problems trying to test it naively in here
# So take this with a grain of salt
# It's what I think might work based on how anchorpy seems to work
class DLOBOrdersCoder:
    def __init__(self, idl: Idl):
        self.idl = idl

    @staticmethod
    def create():
        return DLOBOrdersCoder(dlob_idl)
        
    def encode(self, dlob_orders: DLOBOrders) -> bytes: 
        dlob_order_layout = _field_layout(IdlField('DLOBOrder', IdlTypeDefined), self.idl.types)
        vec_layout = GreedyRange(dlob_order_layout)

        encoded_orders = vec_layout.build(dlob_orders)

        return encoded_orders

    def decode(self, bytes: bytes) -> DLOBOrders:
        dlob_order_layout = _field_layout(IdlField('DLOBOrder', IdlTypeDefined), self.idl.types)
        vec_layout = GreedyRange(dlob_order_layout)

        decoded_orders = vec_layout.parse(bytes)

        return decoded_orders