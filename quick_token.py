#!/usr/bin/env python3
"""Quick token generator - creates .env file with your credentials"""

print("\n" + "="*60)
print("KITE TOKEN SETUP")
print("="*60)

api_key = input("\nEnter your Kite API Key: ").strip()
access_token = input("Enter your Kite Access Token: ").strip()
api_secret = input("Enter your Kite API Secret: ").strip()

if not api_key or not access_token or not api_secret:
    print("\n❌ Error: All fields are required!")
    exit(1)

# Create .env file
env_content = f"""# Kite Connect Credentials
# Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

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
