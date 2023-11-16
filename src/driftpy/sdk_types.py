from dataclasses import dataclass
from solders.pubkey import Pubkey
from borsh_construct.enum import _rust_enum
from sumtypes import constructor
from driftpy.types import *


@_rust_enum
class AssetType:
    QUOTE = constructor()
    BASE = constructor()


@dataclass
class MakerInfo:
    maker: Pubkey
    order: Order
