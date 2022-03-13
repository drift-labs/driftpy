from solana.publickey import PublicKey
from anchorpy import Idl, Program, Provider
from driftpy.constants.config import CONFIG

import os


def load_program(env: str, wallet_path=None):
    assert env in CONFIG.keys()  # , "%s not in %s" % (env, str(CONFIG.keys())))
    CH_PID = CONFIG[env]["CLEARING_HOUSE_PROGRAM_ID"]
    IDL_JSON = None
    IDL_URL = CONFIG[env].get("IDL_URL", None)
    if IDL_URL is None:
        from driftpy.clearing_house import ClearingHouse

        IDL_JSON = ClearingHouse.local_idl()
    else:
        import requests

        print("requesting idl from", IDL_URL)
        IDL_JSON = Idl.from_json(requests.request("GET", IDL_URL).json())

    if "ANCHOR_PROVIDER_URL" not in os.environ:
        if CONFIG[env].get("URL") is not None:
            os.environ["ANCHOR_PROVIDER_URL"] = CONFIG[env]["URL"]

    # override path to wallet
    # os.environ["ANCHOR_WALLET"] = os.path.expanduser("~/.config/solana/.json")
    # del os.environ["ANCHOR_WALLET"]
    p = None
    if wallet_path is not None:
        wallet_path_full = os.path.expanduser(wallet_path)
        assert os.path.exists(wallet_path_full)
        os.environ["ANCHOR_WALLET"] = wallet_path_full
        p = Provider.env()
    else:
        if "ANCHOR_WALLET" not in os.environ:
            print("No solana wallet specified/found. Read-Only mode.")
            p = Provider.readonly(url=os.environ["ANCHOR_PROVIDER_URL"])
        else:
            p = Provider.env()
            # Provider.readonly()
            # raise Exception(
            #     """No solana wallet specified/found. \n
            #     Run `export ANCHOR_WALLET=/path/to/wallet.json`"""
            # )

    # Address of the deployed program.
    program = Program(IDL_JSON, PublicKey(CH_PID), p)
    return program


if __name__ == "__main__":
    program = load_program("devnet-limits")
    # program = load_program('mainnet')
