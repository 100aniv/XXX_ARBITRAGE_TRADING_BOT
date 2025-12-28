"""Upbit API 키 직접 테스트 (D106-3 디버깅)"""
import os
import sys
import json
import uuid
import hashlib
import jwt
import requests
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# .env.live 로드
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / ".env.live"
load_dotenv(env_file, override=True)

# API 키
access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")

print("=" * 70)
print("Upbit API 키 직접 테스트")
print("=" * 70)
print(f"Access Key: {access_key[:8]}...{access_key[-8:]} (길이: {len(access_key)})")
print(f"Secret Key: {secret_key[:8]}...{secret_key[-8:]} (길이: {len(secret_key)})")
print()

# JWT 토큰 생성
payload = {
    'access_key': access_key,
    'nonce': str(uuid.uuid4()),
}

jwt_token = jwt.encode(payload, secret_key, algorithm='HS256')

# API 호출
headers = {"Authorization": f"Bearer {jwt_token}"}
url = "https://api.upbit.com/v1/accounts"

print(f"[요청] {url}")
print(f"[헤더] Authorization: Bearer {jwt_token[:20]}...")
print()

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"[응답] HTTP {response.status_code}")
    print()
    
    if response.status_code == 200:
        print("✅ Upbit API 연결 성공")
        data = response.json()
        print(f"계좌 수: {len(data)}")
        for acc in data:
            print(f"  - {acc.get('currency')}: {acc.get('balance')}")
    else:
        print("❌ Upbit API 연결 실패")
        print()
        print("[응답 바디]")
        print(response.text)
        print()
        
        # JSON 파싱
        try:
            error_data = response.json()
            print("[파싱된 에러]")
            print(json.dumps(error_data, indent=2, ensure_ascii=False))
            
            if "error" in error_data:
                error_name = error_data["error"].get("name")
                error_message = error_data["error"].get("message")
                print()
                print(f"에러 이름: {error_name}")
                print(f"에러 메시지: {error_message}")
        except:
            print("JSON 파싱 실패")
            
except Exception as e:
    print(f"❌ 예외 발생: {e}")
    print(f"타입: {type(e)}")
    if hasattr(e, 'response'):
        print(f"Response: {e.response}")
        if hasattr(e.response, 'text'):
            print(f"Response Text: {e.response.text}")

print()
print("=" * 70)
