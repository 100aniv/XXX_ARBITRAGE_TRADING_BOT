#!/usr/bin/env python3
"""Upbit API 마켓 코드 형식 테스트"""

import requests

# Test 1: KRW-BTC (우리가 수정한 형식)
print("Test 1: KRW-BTC")
try:
    resp = requests.get("https://api.upbit.com/v1/ticker", params={"markets": "KRW-BTC"}, timeout=5)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Data: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50 + "\n")

# Test 2: BTC-KRW (원래 형식)
print("Test 2: BTC-KRW")
try:
    resp = requests.get("https://api.upbit.com/v1/ticker", params={"markets": "BTC-KRW"}, timeout=5)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Data: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")
