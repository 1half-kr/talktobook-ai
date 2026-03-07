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

    # ──────────────────────────────────────────────
    # Cycle 관리 (자서전 챕터 일괄 생성 완료 여부 추적)
    # ──────────────────────────────────────────────

    def init_cycle(self, cycle_id: str, expected_count: int, autobiography_id: int, user_id: int):
        """사이클 초기화 및 Redis 저장.
        cycleId 별로 예상 챕터 수(expectedCount)와 현재까지 완료된 수(completedCount)를 관리한다.
        """
        cycle_data = {
            "expectedCount": expected_count,
            "completedCount": 0,
            "autobiographyId": autobiography_id,
            "userId": user_id,
        }
        try:
            self.redis_client.set(f"cycle:{cycle_id}", json.dumps(cycle_data))
            logger.info(
                f"[CYCLE] Initialized cycle_id={cycle_id} "
                f"expected={expected_count} autobiography_id={autobiography_id}"
            )
        except Exception as e:
            logger.error(f"[CYCLE] Failed to init cycle_id={cycle_id}: {e}")
            raise

    def increment_and_check_cycle(self, cycle_id: str) -> bool:
        """사이클 완료 카운트를 1 증가시키고, 모든 챕터가 완료되었으면 True 반환.
        cycle 정보가 Redis에 없으면 False를 반환한다.
        """
        key = f"cycle:{cycle_id}"
        try:
            data = self.redis_client.get(key)
            if not data:
                logger.warning(f"[CYCLE] Cycle not found cycle_id={cycle_id}")
                return False
            cycle = json.loads(data)
            cycle["completedCount"] += 1
            self.redis_client.set(key, json.dumps(cycle))
            is_last = cycle["completedCount"] >= cycle["expectedCount"]
            logger.info(
                f"[CYCLE] Progress cycle_id={cycle_id} "
                f"completed={cycle['completedCount']} expected={cycle['expectedCount']} is_last={is_last}"
            )
            return is_last
        except Exception as e:
            logger.error(f"[CYCLE] Failed to increment cycle_id={cycle_id}: {e}")
            return False