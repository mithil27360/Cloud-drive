import logging
import sys
from datetime import datetime

# Configure structured logging
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        return str(log_record)

def setup_logging(log_level: str = "INFO"):
    """Configure application logging"""
    logger = logging.getLogger("ai_cloud_drive")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Console handler with JSON format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()
