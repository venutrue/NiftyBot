#!/usr/bin/env python3
##############################################
# GENERATE TOKEN - Kite Connect Authentication
# Run this daily to get a fresh access token
##############################################

import os
import sys
import webbrowser
from kiteconnect import KiteConnect

def main():
    print("=" * 50)
    print("KITE CONNECT TOKEN GENERATOR")
    print("=" * 50)

    # Get API credentials
    api_key = os.environ.get("KITE_API_KEY", "").strip()
    api_secret = os.environ.get("KITE_API_SECRET", "").strip()

    # If not in environment, prompt user
    if not api_key:
        api_key = input("\nEnter your API Key: ").strip()

    if not api_secret:
        api_secret = input("Enter your API Secret: ").strip()

    if not api_key or not api_secret:
        print("\nError: API Key and API Secret are required!")
        print("Get them from: https://developers.kite.trade/apps")
        sys.exit(1)

    # Initialize Kite Connect
    kite = KiteConnect(api_key=api_key)

    # Step 1: Generate login URL
    login_url = kite.login_url()
    print("\n" + "=" * 50)
    print("STEP 1: LOGIN")
    print("=" * 50)
    print(f"\nOpening browser to: {login_url}")
    print("\nIf browser doesn't open, copy this URL manually:")
    print(login_url)

    # Try to open browser
    try:
        webbrowser.open(login_url)
    except:
        pass

    # Step 2: Get request token from redirect URL
    print("\n" + "=" * 50)
    print("STEP 2: GET REQUEST TOKEN")
    print("=" * 50)
    print("\nAfter logging in, you'll be redirected to a URL like:")
    print("https://127.0.0.1/?request_token=XXXX&action=login&status=success")
    print("\nCopy the 'request_token' value from that URL.")

    request_token = input("\nPaste the request_token here: ").strip()

    if not request_token:
        print("Error: Request token is required!")
        sys.exit(1)

    # Step 3: Generate access token
    print("\n" + "=" * 50)
    print("STEP 3: GENERATING ACCESS TOKEN")
    print("=" * 50)

    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]

        print("\n✓ Access token generated successfully!")
        print("\n" + "=" * 50)
        print("YOUR CREDENTIALS")
        print("=" * 50)
        print(f"\nAPI_KEY      = \"{api_key}\"")
        print(f"ACCESS_TOKEN = \"{access_token}\"")
        print(f"API_SECRET   = \"{api_secret}\"")

        # Save to .env file
        env_content = f"""# Kite Connect Credentials
# Generated on: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Access token expires at midnight IST

KITE_API_KEY={api_key}
KITE_ACCESS_TOKEN={access_token}
KITE_API_SECRET={api_secret}
"""

        with open(".env", "w") as f:
            f.write(env_content)

        print("\n✓ Credentials saved to .env file")
        print("\nTo use the bot, run:")
        print("  source .env && python run.py")
        print("\nOr export variables manually:")
        print(f"  export KITE_API_KEY=\"{api_key}\"")
        print(f"  export KITE_ACCESS_TOKEN=\"{access_token}\"")
        print(f"  export KITE_API_SECRET=\"{api_secret}\"")

    except Exception as e:
        print(f"\n✗ Error generating access token: {str(e)}")
        print("\nPossible causes:")
        print("  - Request token expired (valid for only a few minutes)")
        print("  - Incorrect API secret")
        print("  - Request token already used")
        print("\nPlease try again from the beginning.")
        sys.exit(1)

if __name__ == "__main__":
    main()
