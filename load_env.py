#!/usr/bin/env python3
"""
Simple .env file loader
Usage: from load_env import load_env; load_env()
"""

import os

def load_env(filepath=".env"):
    """Load environment variables from .env file."""
    if not os.path.exists(filepath):
        return False

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                os.environ[key] = value

    return True

if __name__ == "__main__":
    if load_env():
        print("Environment variables loaded from .env")
        # Show what was loaded (masking tokens)
        for key in ["KITE_API_KEY", "KITE_ACCESS_TOKEN", "KITE_API_SECRET"]:
            val = os.environ.get(key, "")
            if val:
                masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
                print(f"  {key}: {masked}")
    else:
        print(".env file not found. Run: python generate_token.py")
