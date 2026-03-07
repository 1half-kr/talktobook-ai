import redis
import json
import time
from typing import Dict, Optional, Any
from interviews.interview_chat_v2.dto import MetricsDto
from auth import verify_token
from logs import get_logger

logger = get_logger()

class SessionManager:
    
    def extract_user_id_from_token(self, auth_header: Optional[str]) -> int:
        """JWT 토큰에서 userId 추출"""
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("[AUTH] Invalid authorization header")
            raise ValueError("Invalid authorization header")
        
        token = auth_header.split(" ")[1]
        member_session = verify_token(token)
        logger.debug(f"[AUTH] Extracted user_id={member_session.member_id} from token")
        return member_session.member_id
    
    def generate_session_key(self, user_id: int, autobiography_id: int) -> str:
        """세션 키 생성: {userId}:{autobiographyId}"""
        session_key = f"{user_id}:{autobiography_id}"
        logger.debug(f"[SESSION] Generated session_key={session_key}")
        return session_key
    

    def __init__(self, redis_host: str = None, redis_port: int = None, redis_db: int = 0):
        import os
        # 환경변수에서 Redis 설정 읽기
        redis_host = redis_host or os.getenv('REDIS_HOST')
        redis_port = redis_port or int(os.getenv('REDIS_PORT'))
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.session_ttl = None  # TTL 없음 (영구 저장)
        logger.info(f"[REDIS] Connected to Redis at {redis_host}:{redis_port}")
    
    def save_session(self, session_key: str, metrics: Dict[str, Any], last_question: Optional[Dict[str, Any]] = None):
        """세션 상태 저장"""
        session_data = {
            "metrics": metrics,
            "last_question": last_question,
            "updated_at": time.time()
        }
        try:
            if self.session_ttl:
                self.redis_client.setex(f"session:{session_key}", self.session_ttl, json.dumps(session_data))
            else:
                self.redis_client.set(f"session:{session_key}", json.dumps(session_data))
            logger.info(f"[REDIS] Saved session session_key={session_key}")
        except Exception as e:
            logger.error(f"[REDIS] Failed to save session session_key={session_key}: {e}")
            raise
    
    def load_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        """세션 상태 로드"""
        try:
            data = self.redis_client.get(f"session:{session_key}")
            if data and isinstance(data, str):
                logger.info(f"[REDIS] Loaded session session_key={session_key}")
                return json.loads(data)
            logger.warning(f"[REDIS] Session not found session_key={session_key}")
            return None
        except Exception as e:
            logger.error(f"[REDIS] Failed to load session session_key={session_key}: {e}")
            return None
    
    def create_session(self, session_key: str, user_id: int, autobiography_id: int, preferred_categories: Optional[list] = None, previous_metrics: Optional[Dict] = None):
        """새 세션 생성"""
        if previous_metrics:
            logger.info(f"[SESSION] Creating session with previous metrics session_key={session_key}")
            self.save_session(session_key, previous_metrics, None)
        else:
            initial_metrics = {
                "session_id": session_key,
                "user_id": user_id,
                "autobiography_id": autobiography_id,
                "preferred_categories": preferred_categories or []
            }
            logger.info(f"[SESSION] Creating new session session_key={session_key} user_id={user_id} autobiography_id={autobiography_id}")
            self.save_session(session_key, initial_metrics, None)
    
    def get_session_for_flow(self, session_key: str) -> Dict[str, Any]:
        """flow에 전달할 세션 데이터 반환"""
        session_data = self.load_session(session_key)
        if not session_data:
            logger.debug(f"[SESSION] New session for flow session_key={session_key}")
            return {"sessionId": session_key, "isNewSession": True}
        
        logger.debug(f"[SESSION] Existing session for flow session_key={session_key}")
        return {
            "sessionId": session_key,
            "isNewSession": False,
            "metrics": session_data.get("metrics", {}),
            "last_question": session_data.get("last_question")
        }
    
    def delete_session(self, session_key: str):
        """세션 삭제"""
        try:
            self.redis_client.delete(f"session:{session_key}")
            logger.info(f"[SESSION] Deleted session session_key={session_key}")
        except Exception as e:
            logger.error(f"[REDIS] Failed to delete session session_key={session_key}: {e}")