#!/usr/bin/env python3
"""Test if token generation works and validate credentials"""

import os
from kiteconnect import KiteConnect

print("\n" + "="*60)
print("KITE TOKEN TESTER")
print("="*60)

# Step 1: Get credentials
api_key = input("\nEnter your API Key: ").strip()
api_secret = input("Enter your API Secret: ").strip()

if not api_key or not api_secret:
    print("\n❌ Error: API Key and Secret are required!")
    exit(1)

# Step 2: Generate login URL
kite = KiteConnect(api_key=api_key)
login_url = kite.login_url()

print("\n" + "="*60)
print("STEP 1: LOGIN TO KITE")
print("="*60)
print(f"\nOpen this URL in your browser:\n{login_url}\n")
print("After login, you'll see a URL like:")
print("https://127.0.0.1/?request_token=XXXXX&action=login&status=success")
print("\nCopy the 'request_token' value (XXXXX part)")
print("="*60)

request_token = input("\nPaste the request_token here: ").strip()

if not request_token:
    print("\n❌ Error: Request token is required!")
    exit(1)

# Step 3: Generate session
print("\n" + "="*60)
print("GENERATING ACCESS TOKEN...")
print("="*60)

try:
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]

    print("\n✅ SUCCESS! Access token generated")
    print(f"\nAccess Token: {access_token[:20]}...{access_token[-20:]}")

    # Step 4: Test the token
    print("\n" + "="*60)
    print("TESTING TOKEN...")
    print("="*60)

    kite.set_access_token(access_token)
    profile = kite.profile()

    print(f"\n✅ TOKEN WORKS! Logged in as: {profile['user_name']}")
    print(f"Email: {profile['email']}")

    # Step 5: Save to .env
    print("\n" + "="*60)
    print("SAVING TO .ENV FILE...")
    print("="*60)

    env_content = f"""# Kite Connect Credentials
# Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Token valid until: End of trading day

KITE_API_KEY={api_key}
KITE_ACCESS_TOKEN={access_token}
KITE_API_SECRET={api_secret}
"""

    with open(".env", "w") as f:
        f.write(env_content)

    print("\n✅ Credentials saved to .env file!")
    print("\nYou can now run:")
    print("  python run.py --paper --bot nifty,banknifty")
    print("="*60 + "\n")

except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    print("\nPossible causes:")
    print("  1. Request token expired (valid for only 2 minutes)")
    print("  2. Incorrect API secret")
    print("  3. Request token already used")
    print("  4. API subscription not active")
    print("\nTry again from the beginning")
    exit(1)
