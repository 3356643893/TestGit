from loguru import logger
import sys
from datetime import datetime
from pathlib import Path
from config.config import config

BASE_DIR = Path(__file__).resolve().parent.parent

log_level = config.get("log.log_level", "INFO").upper()
log_dir = BASE_DIR / config.get("log.dir", "reports/logs")

log_dir.mkdir(parents=True, exist_ok=True)

log_file = log_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger.remove()

logger.add(
    str(log_file),
    level=log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    encoding="utf-8",
    rotation=config.get("log.rotation", "10 MB"),
    retention=config.get("log.retention", "7 days"),
    compression="zip"
)

logger.add(
    sys.stdout,
    level=log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

logger.info("Loguru 日志配置加载完成")
