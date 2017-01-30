"""
Logging utils.
"""

import logging
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')
console_stream_handler = logging.StreamHandler()
console_stream_handler.setFormatter(formatter)

def get_logger(name, level = 'info'):
    add_stream_handler()
    logging_level = getattr(logging, level.upper())
    logger = logging.getLogger(name)
    logger.setLevel(logging_level)
    return logger

def add_stream_handler():
    global console_stream_handler
    if len(logging.root.handlers) > 0:
        return
    for handler in logging.root.handlers:
        if handler == console_stream_handler:
            return
    logging.root.addHandler(console_stream_handler)

logger = get_logger('chainscan', 'info')
