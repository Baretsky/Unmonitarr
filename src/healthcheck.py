#!/usr/bin/env python3
"""
Health check script for Unmonitarr Docker container.
This script checks if the application is responding correctly.
"""

import sys
import urllib.request
import urllib.error
import json


def check_health():
    """Check if Unmonitarr is healthy."""
    try:
        # Try to access the health endpoint
        with urllib.request.urlopen('http://localhost:8088/health', timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get('status') == 'healthy':
                    print("✅ Unmonitarr is healthy")
                    return True
                else:
                    print(f"⚠️  Unmonitarr status: {data.get('status', 'unknown')}")
                    return False
            else:
                print(f"❌ HTTP {response.status}")
                return False
                
    except urllib.error.URLError as e:
        print(f"❌ Connection error: {e}")
        return False
    except json.JSONDecodeError:
        print("❌ Invalid JSON response")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    if check_health():
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure