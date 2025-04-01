#!/usr/bin/env python3
"""
Drift Protocol Position and Balance Query Tool

This script provides a comprehensive view of user positions and balances on the Drift Protocol.
It can query information using either a user's authority address or a specific user account address.

Features:
- Display account summary including health, collateral, and leverage
- Show active perpetual positions with market details and PnL
- Show active spot positions with deposit/borrow information
- Display LP (Liquidity Provider) positions and shares
- Real-time market data including oracle prices and AMM state

Requirements:
- Python 3.7+
- Required environment variables:
  * RPC_URL: Solana RPC endpoint URL
  OR
  * Use --rpc command line argument to specify RPC URL directly

Usage Examples:
    # Query by authority address
    ./driftpy-enhanced-usermap.py --authority <AUTHORITY_PUBKEY>

    # Query by specific user account
    ./driftpy-enhanced-usermap.py --account <USER_ACCOUNT_PUBKEY>

    # Use custom RPC endpoint
    ./driftpy-enhanced-usermap.py --authority <PUBKEY> --rpc <RPC_URL>
"""

import os
import asyncio
import argparse
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from anchorpy import Wallet
from dotenv import load_dotenv
from solders.pubkey import Pubkey # type: ignore
from solana.rpc.async_api import AsyncClient

from driftpy.drift_client import DriftClient
from driftpy.drift_user import DriftUser
from driftpy.accounts import DataAndSlot, UserAccount
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig, PollingConfig
from driftpy.constants.numeric_constants import QUOTE_SPOT_MARKET_INDEX
from driftpy.types import SpotPosition, PerpPosition, MarketType
from driftpy.keypair import load_keypair
from driftpy.market_map.market_map import MarketMap
from driftpy.market_map.market_map_config import MarketMapConfig, WebsocketConfig

# Load environment variables
load_dotenv()

@dataclass
class FormattedPosition:
    """Formatted position for better readability"""
    market_index: int
    market_name: str
    market_type: str
    position_size: float
    position_value: float
    entry_price: Optional[float] = None
    pnl: Optional[float] = None
    funding_pnl: Optional[float] = None
    lp_shares: Optional[float] = None
    last_base_asset_amount_per_lp: Optional[float] = None

def format_number(number: float, decimals: int = 2, use_commas: bool = True) -> str:
    """Format a number with proper decimal places and optional comma separators"""
    if abs(number) >= 1e6:
        # For large numbers, use millions format
        return f"{number/1e6:,.{decimals}f}M"
    elif abs(number) >= 1e3 and use_commas:
        return f"{number:,.{decimals}f}"
    else:
        return f"{number:.{decimals}f}"

class EnhancedUserMap:
    """Enhanced UserMap class for accessing and displaying user positions and balances"""
    
    def __init__(self, connection, wallet):
        """Initialize with connection and wallet"""
        self.connection = connection
        self.wallet = wallet
        self.drift_client = DriftClient(connection, wallet)
        self.user_map = None
    
    async def initialize(self):
        """Initialize the drift client and market map"""
        await self.drift_client.subscribe()
        self.user_map = UserMap(
            UserMapConfig(
                self.drift_client,
                PollingConfig(frequency=10000),  # Polling frequency in ms
                self.connection,
                include_idle=True,  # Include idle accounts
            )
        )
        await self.user_map.subscribe()
        
    async def cleanup(self):
        """Clean up connections"""
        if self.user_map:
            await self.user_map.unsubscribe()
        await self.drift_client.unsubscribe()
    
    async def get_user_by_authority(self, authority_pubkey: Pubkey) -> List[DriftUser]:
        """Get all user accounts associated with an authority"""
        if not self.user_map:
            raise ValueError("UserMap not initialized")
        
        users = []
        
        # Sync the user map to fetch all accounts
        await self.user_map.sync()
        
        # Find all accounts with matching authority
        for user in self.user_map.values():
            try:
                user_authority = user.get_user_account().authority
                if str(user_authority) == str(authority_pubkey):
                    users.append(user)
            except Exception as e:
                print(f"Error checking user authority: {e}")
        
        return users
    
    async def get_user_by_account(self, user_account_pubkey: Pubkey) -> Optional[DriftUser]:
        """Get a specific user account by its address"""
        if not self.user_map:
            raise ValueError("UserMap not initialized")
        
        # Sync the user map to fetch all accounts
        await self.user_map.sync()
        
        # Find the specific user account
        return self.user_map.get(str(user_account_pubkey))
    
    def format_perp_position(self, user: DriftUser, position: PerpPosition) -> FormattedPosition:
        """Format a perpetual position for display"""
        market = self.drift_client.get_perp_market_account(position.market_index)
        oracle_price_data = user.get_oracle_data_for_perp_market(position.market_index)
        
        # Decode market name from bytes
        market_name = bytes(market.name).decode('utf-8').strip('\x00')
        
        # Get position value in USD
        position_value = user.get_perp_position_value(
            position.market_index, 
            oracle_price_data,
            include_open_orders=True
        )
        
        # Calculate base asset amount with precision adjustment
        base_asset_amount = position.base_asset_amount / 1e9  # BASE_PRECISION
        
        # Calculate entry price if possible
        entry_price = None
        if position.base_asset_amount != 0:
            entry_price = abs(position.quote_entry_amount / position.base_asset_amount * 1e9)
        
        # Calculate unrealized PnL
        unrealized_pnl = user.get_unrealized_pnl(
            with_funding=False,
            market_index=position.market_index
        ) / 1e6  # QUOTE_PRECISION
        
        # Calculate funding PnL
        funding_pnl = user.get_unrealized_funding_pnl(
            market_index=position.market_index
        ) / 1e6  # QUOTE_PRECISION

        # Get LP information
        lp_shares = position.lp_shares / 1e9 if position.lp_shares != 0 else 0
        last_base_per_lp = position.last_base_asset_amount_per_lp / 1e9 if position.last_base_asset_amount_per_lp != 0 else 0
        
        return FormattedPosition(
            market_index=position.market_index,
            market_name=market_name,
            market_type="Perpetual",
            position_size=base_asset_amount,
            position_value=position_value / 1e6,  # QUOTE_PRECISION
            entry_price=entry_price,
            pnl=unrealized_pnl,
            funding_pnl=funding_pnl,
            lp_shares=lp_shares,
            last_base_asset_amount_per_lp=last_base_per_lp
        )
    
    def format_spot_position(self, user: DriftUser, position: SpotPosition) -> FormattedPosition:
        """Format a spot market position for display"""
        market = self.drift_client.get_spot_market_account(position.market_index)
        oracle_price_data = user.get_oracle_data_for_spot_market(position.market_index)
        
        # Decode market name from bytes
        market_name = bytes(market.name).decode('utf-8').strip('\x00')
        
        # Get token amount with proper sign (positive for deposits, negative for borrows)
        token_amount = user.get_token_amount(position.market_index)
        
        # Convert to human readable format based on decimals
        decimals = market.decimals
        formatted_token_amount = token_amount / (10 ** decimals)
        
        # Calculate token value in USD
        token_value = 0
        if position.market_index == QUOTE_SPOT_MARKET_INDEX:
            # For USDC, the value is just the token amount
            token_value = abs(formatted_token_amount)
        else:
            # For other tokens, calculate USD value
            base_value = user.get_spot_market_asset_value(
                market_index=position.market_index,
                include_open_orders=True
            ) / 1e6  # QUOTE_PRECISION
            if token_amount < 0:
                liability_value = user.get_spot_market_liability_value(
                    market_index=position.market_index,
                    include_open_orders=True
                ) / 1e6  # QUOTE_PRECISION
                token_value = liability_value
            else:
                token_value = base_value
        
        return FormattedPosition(
            market_index=position.market_index,
            market_name=market_name,
            market_type="Spot",
            position_size=formatted_token_amount,
            position_value=token_value
        )
    
    async def get_formatted_positions(self, user: DriftUser) -> Dict[str, List[FormattedPosition]]:
        """Get formatted positions for a user"""
        result = {
            "perp_positions": [],
            "spot_positions": []
        }
        
        # Get active perpetual positions
        perp_positions = user.get_active_perp_positions()
        for position in perp_positions:
            formatted = self.format_perp_position(user, position)
            result["perp_positions"].append(formatted)
        
        # Get active spot positions
        spot_positions = user.get_active_spot_positions()
        for position in spot_positions:
            formatted = self.format_spot_position(user, position)
            result["spot_positions"].append(formatted)
        
        return result
    
    async def get_account_summary(self, user: DriftUser) -> Dict[str, Any]:
        """Get summary information about the user account"""
        user_account = user.get_user_account()
        
        # Calculate collateral and margin requirements
        total_collateral = user.get_total_collateral() / 1e6
        margin_requirement = user.get_margin_requirement() / 1e6
        free_collateral = user.get_free_collateral() / 1e6
        
        # Get health info
        health = user.get_health()
        
        # Get leverage
        leverage = user.get_leverage() / 10000  # Convert from basis points to x format
        
        # Get authority's pubkey as string
        authority = str(user_account.authority)
        
        # Get subaccount id
        subaccount_id = user_account.sub_account_id
        
        # Get settled PnL
        settled_pnl = user.get_settled_perp_pnl() / 1e6
        
        # Get account value
        net_usd_value = user.get_net_usd_value() / 1e6
        
        return {
            "authority": authority,
            "sub_account_id": subaccount_id,
            "account_health": health,
            "total_collateral": total_collateral,
            "margin_requirement": margin_requirement,
            "free_collateral": free_collateral,
            "leverage": leverage,
            "settled_pnl": settled_pnl,
            "net_usd_value": net_usd_value
        }

def print_summary(summary: Dict[str, Any]):
    """
    Print a formatted summary of the user account.
    
    Args:
        summary: Dictionary containing account summary information including:
            - authority: Authority public key
            - sub_account_id: Sub-account identifier
            - account_health: Health percentage
            - total_collateral: Total collateral in USD
            - margin_requirement: Required margin in USD
            - free_collateral: Available collateral in USD
            - leverage: Current account leverage
            - settled_pnl: Settled PnL in USD
            - net_usd_value: Net account value in USD
    """
    print("\n=== Account Summary ===")
    print(f"Authority: {summary['authority']}")
    print(f"Sub Account ID: {summary['sub_account_id']}")
    print(f"Account Health: {summary['account_health']}%")
    print(f"Total Collateral: ${format_number(summary['total_collateral'])}")
    print(f"Margin Requirement: ${format_number(summary['margin_requirement'])}")
    print(f"Free Collateral: ${format_number(summary['free_collateral'])}")
    print(f"Leverage: {format_number(summary['leverage'], 2, False)}x")
    print(f"Settled PnL: ${format_number(summary['settled_pnl'])}")
    print(f"Net USD Value: ${format_number(summary['net_usd_value'])}")

def print_positions(positions: Dict[str, List[FormattedPosition]], drift_client: DriftClient):
    """
    Print formatted position information for both spot and perpetual markets.
    
    Args:
        positions: Dictionary containing lists of spot and perpetual positions
        drift_client: DriftClient instance for fetching market data
    
    Displays:
        For Spot Positions:
        - Market name and index
        - Position type (Deposit/Borrow)
        - Size and USD value
        - Market status and asset information
        - Total deposits and borrows
        
        For Perpetual Positions:
        - Market name and index
        - Position type (Long/Short)
        - Size, entry price, and USD value
        - Unrealized PnL and funding PnL
        - Market status and contract information
        - AMM state and LP information if applicable
    """
    # Print spot positions
    if positions["spot_positions"]:
        print("\n=== Spot Positions ===")
        for pos in positions["spot_positions"]:
            try:
                position_type = "Deposit" if pos.position_size > 0 else "Borrow"
                market = drift_client.get_spot_market_account(pos.market_index)
                
                print(f"Market: {pos.market_name} (Index: {pos.market_index})")
                print(f"Type: {position_type}")
                print(f"Size: {format_number(abs(pos.position_size), 6, False)}")
                print(f"Value: ${format_number(abs(pos.position_value))}")
                
                # Display market info if available
                if market:
                    print(f"Market Status: {market.status.__class__.__name__}")
                    print(f"Asset Tier: {market.asset_tier.__class__.__name__}")
                    print(f"Oracle Source: {market.oracle_source.__class__.__name__}")
                    print(f"Total Deposits: {format_number(market.deposit_balance / (10 ** market.decimals))}")
                    print(f"Total Borrows: {format_number(market.borrow_balance / (10 ** market.decimals))}")
            except Exception as e:
                print(f"Warning: Could not fetch complete market data: {str(e)}")
            print("---")
    else:
        print("\nNo spot positions found.")
    
    # Print perpetual positions
    if positions["perp_positions"]:
        print("\n=== Perpetual Positions ===")
        for pos in positions["perp_positions"]:
            try:
                position_type = "Long" if pos.position_size > 0 else "Short"
                market = drift_client.get_perp_market_account(pos.market_index)
                
                print(f"Market: {pos.market_name} (Index: {pos.market_index})")
                print(f"Type: {position_type}")
                print(f"Size: {format_number(abs(pos.position_size), 6, False)}")
                print(f"Entry Price: ${format_number(pos.entry_price)}" if pos.entry_price else "Entry Price: N/A")
                print(f"Value: ${format_number(abs(pos.position_value))}")
                print(f"Unrealized PnL: ${format_number(pos.pnl)}")
                print(f"Funding PnL: ${format_number(pos.funding_pnl)}")
                
                # Display market info if available
                if market:
                    print(f"Market Status: {market.status.__class__.__name__}")
                    print(f"Contract Type: {market.contract_type.__class__.__name__}")
                    print(f"Oracle Source: {market.amm.oracle_source.__class__.__name__}")
                    print(f"24h Volume: {format_number(market.amm.volume24h / 1e6)}M")
                    print(f"AMM Base Reserve: {format_number(market.amm.base_asset_reserve / 1e9, 4)}")
                    print(f"AMM Quote Reserve: {format_number(market.amm.quote_asset_reserve / 1e6, 4)}")
                    print(f"Total LP Shares: {format_number(market.amm.user_lp_shares / 1e9, 4)}")
                    if pos.lp_shares and pos.lp_shares > 0:
                        print(f"Your LP Shares: {format_number(pos.lp_shares, 4)}")
                        if pos.last_base_asset_amount_per_lp:
                            print(f"Your LP Base Per Share: {format_number(pos.last_base_asset_amount_per_lp, 4)}")
            except Exception as e:
                print(f"Warning: Could not fetch complete market data: {str(e)}")
            print("---")
    else:
        print("\nNo perpetual positions found.")

async def find_and_display_user_data(enhanced_map: EnhancedUserMap, address: str, is_authority: bool):
    """Find and display user data for given address"""
    pubkey = Pubkey.from_string(address)
    
    users = []
    if is_authority:
        users = await enhanced_map.get_user_by_authority(pubkey)
        if not users:
            print(f"No accounts found for authority: {address}")
            return
        print(f"Found {len(users)} sub-account(s) for authority {address}")
    else:
        user = await enhanced_map.get_user_by_account(pubkey)
        if not user:
            print(f"No user account found at address: {address}")
            return
        users = [user]
    
    # Process each user account
    for i, user in enumerate(users):
        if len(users) > 1:
            print(f"\n==== Sub-Account {i} ====")
        
        # Get account summary
        summary = await enhanced_map.get_account_summary(user)
        print_summary(summary)
        
        # Get and display positions
        positions = await enhanced_map.get_formatted_positions(user)
        print_positions(positions, enhanced_map.drift_client)

async def main():
    """
    Main function to process command line arguments and display user positions.
    
    Command Line Arguments:
        --authority: Authority public key to query all associated accounts
        --account: Specific user account public key to query
        --rpc: Optional RPC URL (overrides RPC_URL environment variable)
    
    Environment Variables:
        RPC_URL: Required if --rpc not provided. Solana RPC endpoint URL.
    
    The script will:
    1. Connect to the Drift Protocol
    2. Query user account(s)
    3. Display account summary
    4. Show all active positions with detailed market information
    """
    parser = argparse.ArgumentParser(
        description="Query Drift Protocol for positions and balances",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Query by authority address
    %(prog)s --authority <AUTHORITY_PUBKEY>
    
    # Query specific user account
    %(prog)s --account <USER_ACCOUNT_PUBKEY>
    
    # Use custom RPC endpoint
    %(prog)s --authority <PUBKEY> --rpc <RPC_URL>

Notes:
    - Either --authority or --account must be provided
    - RPC URL must be provided either via --rpc or RPC_URL environment variable
    - For accurate results, ensure the RPC endpoint is reliable and up-to-date
    """
    )
    
    # Define the arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--authority", help="Authority public key to query")
    group.add_argument("--account", help="User account public key to query")
    
    parser.add_argument("--rpc", help="RPC URL (will use RPC_URL env var if not provided)")
    
    # Parse the arguments
    args = parser.parse_args()
    
    # Get RPC URL
    rpc_url = args.rpc or os.environ.get("RPC_URL")
    if not rpc_url:
        print("Error: RPC URL is required. Either set the RPC_URL environment variable or use --rpc")
        return
    
    # Create a dummy keypair - we're only reading data, not signing transactions
    from solders.keypair import Keypair
    kp = Keypair()
    wallet = Wallet(kp)
    
    # Setup connection
    connection = AsyncClient(rpc_url)
    
    # Create enhanced user map
    enhanced_map = EnhancedUserMap(connection, wallet)
    
    try:
        # Initialize
        await enhanced_map.initialize()
        
        if args.authority:
            await find_and_display_user_data(enhanced_map, args.authority, True)
        else:  # args.account
            await find_and_display_user_data(enhanced_map, args.account, False)
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Clean up
        await enhanced_map.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 