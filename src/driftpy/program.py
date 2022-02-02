from solana.publickey import PublicKey
from anchorpy import Idl, Program, Provider
from driftpy.constants.config import CONFIG

import os
import requests


def load_program(env: str, wallet_path=None):
    assert (env in CONFIG.keys(), "%s not in %s" % (env, str(CONFIG.keys())))

    CH_PID = CONFIG[env].get("CLEARING_HOUSE_PROGRAM_ID")
    IDL_JSON = None
    IDL_URL = CONFIG[env].get("IDL_URL", None)
    if IDL_URL is None:
        from driftpy.clearing_house import ClearingHouse

        IDL_JSON = ClearingHouse.local_idl()
    else:
        print("requesting idl from", IDL_URL)
        IDL_JSON = Idl.from_json(requests.request("GET", IDL_URL).json())

    if "ANCHOR_PROVIDER_URL" not in os.environ:
        os.environ["ANCHOR_PROVIDER_URL"] = CONFIG[env].get("URL")

    # override path to wallet
    # os.environ["ANCHOR_WALLET"] = os.path.expanduser("~/.config/solana/<YOURWALLETNAME>.json")
    # del os.environ["ANCHOR_WALLET"]
    if wallet_path is not None:
        wallet_path_full = os.path.expanduser(wallet_path)
        assert os.path.exists(wallet_path_full)
        os.environ["ANCHOR_WALLET"] = wallet_path_full
    else:
        if "ANCHOR_WALLET" not in os.environ:
            raise (
                "No solana wallet specified/found. Run `export ANCHOR_WALLET=/path/to/wallet.json`"
            )

    # Address of the deployed program.
    program = Program(IDL_JSON, PublicKey(CH_PID), Provider.env())
    return program


if __name__ == "__main__":
    program = load_program("devnet-limits")
    # program = load_program('mainnet')
