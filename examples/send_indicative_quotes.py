import asyncio
import logging
import os

import requests
from dotenv import load_dotenv

from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
from driftpy.indicative_quotes import IndicativeQuotesSender, Quote
from driftpy.keypair import load_keypair

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def get_current_price():
    """Get current market price from API"""
    # NOTE: If you want to send to the actual dlob and not staging,
    # remove the `staging.` from the url
    response = requests.get(
        "https://staging.dlob.drift.trade/l2?includeIndicative=true&marketName=SOL-PERP",
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    data = response.json()
    return float(data["oracle"]) / PRICE_PRECISION


def check_my_quotes(expected_size: str):
    """Check if quotes are in the orderbook"""
    try:
        response = requests.get(
            "https://staging.dlob.drift.trade/l2?includeIndicative=true&marketName=SOL-PERP"
        )
        response.raise_for_status()
        data = response.json()

        my_bid = None
        my_ask = None

        if "bids" in data:
            my_bid = next(
                (
                    bid
                    for bid in data["bids"]
                    if bid.get("sources", {}).get("indicative") == expected_size
                ),
                None,
            )

        if "asks" in data:
            my_ask = next(
                (
                    ask
                    for ask in data["asks"]
                    if ask.get("sources", {}).get("indicative") == expected_size
                ),
                None,
            )

        return {"bid_found": bool(my_bid), "ask_found": bool(my_ask)}
    except Exception:
        return {"bid_found": False, "ask_found": False}


async def main():
    endpoint = "https://staging.dlob.drift.trade"
    keypair = load_keypair(os.getenv("PRIVATE_KEY"))
    quote_endpoint = endpoint.replace("https://", "wss://") + "/quotes/ws"
    quoter = IndicativeQuotesSender(quote_endpoint, keypair)

    logger.info("Connecting to quote server...")

    asyncio.create_task(quoter.connect())
    await asyncio.sleep(3)

    quote_count = 0
    current_base_price = 171.25  # Will be overwritten by current market price

    logger.info("Started sending indicative quotes every 2 seconds...")

    while True:
        try:
            quote_count += 1

            if quote_count % 5 == 1:
                current_base_price = get_current_price()
                logger.info(
                    f"[{quote_count}] Updated base price to: {current_base_price:.6f}"
                )

            spread_bps = 0.01  # 1% spread
            bid_price = current_base_price * (1 - spread_bps)
            ask_price = current_base_price * (1 + spread_bps)

            bid_size = 1.353535353535
            ask_size = 1.353535353535

            bid_price_scaled = int(bid_price * PRICE_PRECISION)
            ask_price_scaled = int(ask_price * PRICE_PRECISION)
            bid_size_scaled = int(bid_size * BASE_PRECISION)
            ask_size_scaled = int(ask_size * BASE_PRECISION)

            quote = Quote(
                bid_price=bid_price_scaled,
                ask_price=ask_price_scaled,
                bid_base_asset_amount=bid_size_scaled,
                ask_base_asset_amount=ask_size_scaled,
                market_index=0,
                is_oracle_offset=False,
            )

            quoter.set_quote(quote)

            logger.info(
                f"[{quote_count}] Raw: bid={bid_price:.6f} ask={ask_price:.6f} "
                f"bidSize={bid_size} askSize={ask_size}"
            )
            logger.info(
                f"[{quote_count}] Scaled: bid={bid_price_scaled} ask={ask_price_scaled} "
                f"bidSize={bid_size_scaled} askSize={ask_size_scaled}"
            )

            # Just for fun, we can check if quotes are in orderbook

            logger.info(f"[{quote_count}] Checking orderbook...")
            check = check_my_quotes(str(bid_size_scaled))
            bid_status = "✅" if check["bid_found"] else "❌"
            ask_status = "✅" if check["ask_found"] else "❌"
            logger.info(
                f"[{quote_count}] {bid_status} Bid {ask_status} Ask in orderbook"
            )

            await asyncio.sleep(2.0)

        except KeyboardInterrupt:
            logger.info("Stopping quote sender...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(2.0)

    await quoter.close()


if __name__ == "__main__":
    asyncio.run(main())
