#!/usr/bin/env python3
"""Generate Kite login URL"""

api_key = input("Enter your API Key: ").strip()

if not api_key:
    print("API Key is required!")
    exit(1)

login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}"

print("\n" + "="*60)
print("STEP 1: Open this URL in your browser:")
print("="*60)
print(f"\n{login_url}\n")
print("="*60)
print("\nSTEP 2: After login, you'll be redirected to a URL like:")
print("https://127.0.0.1/?request_token=XXXXX&action=login&status=success")
print("\nCopy the 'request_token' value (the XXXXX part)")
print("="*60 + "\n")
