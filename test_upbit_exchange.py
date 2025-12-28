"""Upbit Exchange 클래스 직접 테스트"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env.live 로드
env_file = Path(__file__).parent / ".env.live"
load_dotenv(env_file, override=True)

# Exchange import
from arbitrage.exchanges.upbit_spot import UpbitSpotExchange

# API 키
access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")

print("=" * 70)
print("Upbit Exchange 클래스 테스트")
print("=" * 70)
print(f"Access Key: {access_key[:8]}...{access_key[-8:]} (길이: {len(access_key)})")
print(f"Secret Key: {secret_key[:8]}...{secret_key[-8:]} (길이: {len(secret_key)})")
print()

# Exchange 초기화
upbit = UpbitSpotExchange(config={
    "api_key": access_key,
    "api_secret": secret_key,
    "live_enabled": False
})

print(f"Exchange 초기화 완료")
print(f"  - self.api_key: {upbit.api_key[:8]}...{upbit.api_key[-8:]}")
print(f"  - self.api_secret: {upbit.api_secret[:8]}...{upbit.api_secret[-8:]}")
print()

# get_balance 호출
try:
    balance = upbit.get_balance()
    print("✅ get_balance() 성공")
    print(f"계좌 수: {len(balance)}")
    for asset, bal in list(balance.items())[:3]:
        print(f"  - {asset}: {bal.free}")
except Exception as e:
    print(f"❌ get_balance() 실패")
    print(f"에러: {e}")
    print(f"타입: {type(e).__name__}")

print()
print("=" * 70)
