import base64
import json
import hmac
import hashlib

# 간단한 JWT 토큰 생성
SECRET_KEY = "0190ab45-7e42-7a3f-9dec-726ddf778076"

header = {"alg": "HS256", "typ": "JWT"}
payload = {"memberId": 1, "roles": ["MEMBER"]}

# Base64 인코딩
header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')

# 서명 생성
message = f"{header_b64}.{payload_b64}"
signature = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).digest()
signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')

token = f"{header_b64}.{payload_b64}.{signature_b64}"

print("=== Test JWT Token ===")
print(token)
print("\n=== Swagger Authorization에서 사용 ===")
print("Bearer 없이 토큰만 입력:")
print(token)