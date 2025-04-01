# Import required libraries
# asyncio for asynchronous programming
import asyncio
# os for interacting with the operating system, particularly for environment variables
import os
# csv for handling CSV file operations
import csv
# datetime for generating timestamps
from datetime import datetime

# Importing necessary classes from the Anchor and Solana libraries
from anchorpy import Wallet
from dotenv import load_dotenv  # For loading environment variables from a .env file
from solana.rpc.async_api import AsyncClient  # Asynchronous client for Solana RPC

# Importing classes from the Drift protocol library
from driftpy.drift_client import DriftClient  # Client to interact with the Drift protocol
from driftpy.user_map.user_map import UserMap  # Class to manage user states in Drift
from driftpy.user_map.user_map_config import UserMapConfig  # Configuration for UserMap
from driftpy.user_map.user_map_config import (
    WebsocketConfig as UserMapWebsocketConfig,  # Websocket configuration for UserMap
)

async def get_user_map():
    """Initialize and return the UserMap instance."""
    # Load environment variables and get RPC URL
    load_dotenv()
    url = os.getenv("RPC_URL")
    
    if not url:
        raise ValueError("RPC_URL not found in environment variables. Please check your .env file.")
    
    try:
        # Initialize connection and drift client
        connection = AsyncClient(url, timeout=30)
        await connection.is_connected()
        
        dc = DriftClient(
            connection,
            Wallet.dummy(),
            "mainnet",
        )
        await dc.subscribe()
        
        # Initialize and subscribe to UserMap
        user_map = UserMap(UserMapConfig(dc, UserMapWebsocketConfig()))
        await user_map.subscribe()
        
        return user_map
    
    except Exception as e:
        print(f"Error initializing connection: {str(e)}")
        raise

def normalize_authority(authority):
    """Normalize authority string for consistent comparison."""
    if not authority:
        return ""
    authority_str = str(authority)
    # Remove any whitespace and convert to lowercase
    return authority_str.strip().lower()

def load_authorities_from_csv(filename):
    """
    Load top 200 authorities from the fuel breakdown CSV file,
    sorted by depositFuel in descending order.
    """
    authority_data = []
    try:
        with open(filename, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            # Verify that required columns exist
            required_columns = ['authority', 'depositFuel']
            if not all(col in reader.fieldnames for col in required_columns):
                raise ValueError("CSV file must contain both 'authority' and 'depositFuel' columns")
            
            # Extract authority and depositFuel, converting depositFuel to float
            for row in reader:
                if row['authority'] and row['depositFuel']:  # Only add non-empty entries
                    try:
                        deposit_fuel = float(row['depositFuel'])
                        authority_data.append({
                            'authority': normalize_authority(row['authority']),  # Normalized
                            'depositFuel': deposit_fuel,
                            'original_authority': row['authority']  # Keep original for output
                        })
                    except ValueError:
                        print(f"Warning: Invalid depositFuel value for authority {row['authority']}, skipping")
                        continue
        
        # Sort by depositFuel in descending order and take top 200
        sorted_authorities = sorted(authority_data, key=lambda x: x['depositFuel'], reverse=True)[:200]
        
        # Create a list of tuples with normalized and original authorities
        top_200_authorities = [(item['authority'], item['original_authority']) for item in sorted_authorities]
        
        print(f"Successfully loaded top 200 authorities from {filename}, sorted by depositFuel")
        return top_200_authorities
    
    except FileNotFoundError:
        print(f"Error: Could not find CSV file at {filename}")
        raise
    except ValueError as ve:
        print(f"Error with CSV format: {str(ve)}")
        raise
    except Exception as e:
        print(f"Error reading authorities from CSV: {str(e)}")
        raise

async def lookup_user_accounts(authorities):
    """
    Look up user accounts for given authorities.
    
    Args:
        authorities (list): List of authority addresses to look up
        
    Returns:
        list: List of dictionaries containing authority and associated user accounts
    """
    try:
        # Get UserMap instance
        print("Initializing UserMap...")
        user_map = await get_user_map()
        
        # Normalize input authorities
        normalized_authorities = [(normalize_authority(auth), auth) for auth in authorities]
        
        # Create results list to store authority-user mappings
        results = []
        total_authorities = len(normalized_authorities)
        
        # Build authority lookup map for efficient processing
        print("\nBuilding authority lookup map...")
        authority_lookup = {}
        skipped_count = 0
        for user_key, user in user_map.user_map.items():
            try:
                auth = user_map.get_user_authority(user_key)
                if auth:
                    norm_auth = normalize_authority(auth)
                    if norm_auth not in authority_lookup:
                        authority_lookup[norm_auth] = []
                    authority_lookup[norm_auth].append(str(user_key))
            except Exception as e:
                skipped_count += 1
                print(f"Warning: Skipped user {str(user_key)[:8]}... due to: {str(e)}")
                continue
        
        if skipped_count > 0:
            print(f"Warning: Skipped {skipped_count} users while building lookup map")
        
        # Process each authority
        print("\nProcessing authorities...")
        for idx, (norm_authority, orig_authority) in enumerate(normalized_authorities, 1):
            print(f"Processing {idx}/{total_authorities}: {orig_authority[:8]}...")
            try:
                found_users = authority_lookup.get(norm_authority, [])
                
                if found_users:
                    for user_account in found_users:
                        results.append({
                            'authority': orig_authority,
                            'user_account': user_account
                        })
                    print(f"  ✓ Found {len(found_users)} user account(s).")
                else:
                    results.append({
                        'authority': orig_authority,
                        'user_account': 'No user accounts found'
                    })
                    print(f"  - No user accounts found")
            
            except Exception as e:
                print(f"  ✗ Error processing authority: {str(e)}")
                results.append({
                    'authority': orig_authority,
                    'user_account': f'Error processing authority: {str(e)}'
                })
        
        # Print summary statistics
        print("\nProcessing complete!")
        authorities_with_matches = sum(
            1 
            for r in results 
            if r['user_account'] != 'No user accounts found'
        )
        print(f"Found matches for {authorities_with_matches} out of {total_authorities} authorities")
        
        return results
        
    except Exception as e:
        print(f"Error in lookup execution: {str(e)}")
        raise

async def main():
    """
    Example usage of the lookup_user_accounts function.
    Replace the example authorities with actual ones you want to look up.
    """
    # Example authorities to look up
    example_authorities = [
        "FULqR3GHUtHBxjhVHRSg7u1JXvBxQNPZGS9fnhqt8YEk",
        "8SSLjXBR1acDjvKjJsGGWEhMoMHwvPxiJx9uoGQsDUNo"
    ]
    
    results = await lookup_user_accounts(example_authorities)
    return results

if __name__ == "__main__":
    try:
        print("\n=== Authority to User Account Lookup ===\n")
        results = asyncio.run(main())
        print("\n=== Processing Complete ===\n")
        
    except Exception as e:
        print(f"\n✗ Fatal error: {str(e)}")