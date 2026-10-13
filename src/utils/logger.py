import logging
import sys

def get_logger(name: str = "news_sentiment_agent") -> logging.Logger:
    """
    Configure and return a structured logger instance.

    Args:
        name (str): Logger name.

    Returns:
        logging.Logger: Configured logger.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = get_logger()
