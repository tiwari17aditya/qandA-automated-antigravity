import os
import sys
import logging
from datetime import datetime

_LOGGERS = {}

def get_pipeline_logger(job_name: str, pipeline_id: str = "global"):
    """
    Returns a configured logger instance that logs formatted messages to stdout
    and saves dedicated log files into the 'logs/' folder per pipeline.
    """
    logger_key = f"{job_name}_{pipeline_id}"
    if logger_key in _LOGGERS:
        return _LOGGERS[logger_key]

    logger = logging.getLogger(logger_key)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Ensure logs directory exists
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_filename = os.path.join(logs_dir, f"{job_name}_{pipeline_id}.log")

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(pipeline)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File Handler
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console (stdout) Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    class PipelineAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            kwargs["extra"] = kwargs.get("extra", {})
            kwargs["extra"]["pipeline"] = pipeline_id
            return msg, kwargs

    adapter = PipelineAdapter(logger, {})
    _LOGGERS[logger_key] = adapter
    return adapter

def log_info(job_name: str, pipeline_id: str, message: str):
    logger = get_pipeline_logger(job_name, pipeline_id)
    logger.info(message)

def log_warn(job_name: str, pipeline_id: str, message: str):
    logger = get_pipeline_logger(job_name, pipeline_id)
    logger.warning(message)

def log_error(job_name: str, pipeline_id: str, message: str):
    logger = get_pipeline_logger(job_name, pipeline_id)
    logger.error(message)
