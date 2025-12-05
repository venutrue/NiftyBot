#!/usr/bin/env python3
"""Convert request_token to access_token"""

from kiteconnect import KiteConnect

print("\n" + "="*60)
print("CONVERT REQUEST TOKEN TO ACCESS TOKEN")
print("="*60)

api_key = input("\nEnter your API Key: ").strip()
api_secret = input("Enter your API Secret: ").strip()
request_token = input("Enter the request_token from URL: ").strip()

if not api_key or not api_secret or not request_token:
    print("\n❌ Error: All fields are required!")
    exit(1)

try:
    kite = KiteConnect(api_key=api_key)
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]

    # Create .env file
    env_content = f"""# Kite Connect Credentials
# Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

KITE_API_KEY={api_key}
KITE_ACCESS_TOKEN={access_token}
KITE_API_SECRET={api_secret}
"""

    with open(".env", "w") as f:
        f.write(env_content)

    print("\n✅ Success! Access token generated and saved to .env")
    print(f"\nAccess Token: {access_token}")
    print("\nYou can now run:")
    print("  python run.py --paper --bot nifty,banknifty")
    print("="*60 + "\n")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    print("\nPossible causes:")
    print("  - Request token expired (valid for only 2 minutes)")
    print("  - Incorrect API secret")
    print("  - Request token already used")
    print("\nTry again from Step 1")
    exit(1)
