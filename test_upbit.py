import os
import json
import uuid
import jwt
import requests
from pathlib import Path
from dotenv import load_dotenv

env_file = Path(__file__).parent / ".env.live"
load_dotenv(env_file, override=True)

access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")

print("=" * 70)
print("Upbit API 키 직접 테스트")
print("=" * 70)
print(f"Access Key: {access_key[:8]}...{access_key[-8:]} (길이: {len(access_key)})")
print(f"Secret Key: {secret_key[:8]}...{secret_key[-8:]} (길이: {len(secret_key)})")
print()

payload = {
    "access_key": access_key,
    "nonce": str(uuid.uuid4()),
}

jwt_token = jwt.encode(payload, secret_key, algorithm="HS256")
headers = {"Authorization": f"Bearer {jwt_token}"}
url = "https://api.upbit.com/v1/accounts"

print(f"[요청] {url}")
print()

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"[응답] HTTP {response.status_code}")
    print()
    
    if response.status_code == 200:
        print("✅ Upbit API 연결 성공")
        data = response.json()
        print(f"계좌 수: {len(data)}")
        for acc in data[:3]:
            print(f"  - {acc.get('currency')}: {acc.get('balance')}")
    else:
        print("❌ Upbit API 연결 실패")
        print()
        print("[응답 바디]")
        print(response.text)
        print()
        
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
        except Exception as parse_err:
            print(f"JSON 파싱 실패: {parse_err}")
            
except Exception as e:
    print(f"❌ 예외 발생: {e}")
    print(f"타입: {type(e).__name__}")

print()
print("=" * 70)
