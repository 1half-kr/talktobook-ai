import logging
import os
import sys
import json
from logging import handlers
from datetime import datetime

# Global variable to store the logger instance
_logger = None
class JSONFormatter(logging.Formatter):
    """JSON 포맷터 - Promtail/Loki용"""
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 추가 필드가 있으면 포함
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # 예외 정보가 있으면 포함
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def get_logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger("life-bookshelf-ai")
                
        # 환경변수로 로그 레벨 설정 (기본: INFO)
        log_level = os.environ.get("LOG_LEVEL", "INFO")
        _logger.setLevel(getattr(logging, log_level))
        
        # JSON 포맷터
        json_formatter = JSONFormatter()
        
        # 기존 포맷터 (파일용)
        text_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        
        # 1. stdout 핸들러 (Promtail이 수집) - JSON 포맷
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(json_formatter)
        _logger.addHandler(console_handler)
        
        # 2. 파일 핸들러 (백업용) - 텍스트 포맷
        log_dir = os.environ.get("LOG_DIR", "/var/log/ai-server")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = handlers.RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(text_formatter)
        _logger.addHandler(file_handler)

    return _logger
