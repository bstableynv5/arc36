import logging
import sys
from datetime import datetime as dt  # broken for no reason
from pathlib import Path
from typing import Any, Generator, Literal, Optional, Union

import arcpy
from formats import PSEUDO_ISO_FMT, EXTRA_PSEUDO_ISO_FMT

# save these for logger before kibana (from toolbox import) clobbers things
real_stdout = sys.stdout
real_stderr = sys.stderr


class OutputCapture:
    """Capture arcpy tool output to a logger."""

    _orig_message = arcpy.AddMessage  # real arcpy funcs?
    _orig_warning = arcpy.AddWarning
    _orig_error = arcpy.AddError

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def __enter__(self) -> logging.Logger:
        arcpy.AddMessage = self._message
        arcpy.AddWarning = self._warning
        arcpy.AddError = self._error
        return self.logger

    def __exit__(self, exc_type, exc_value, traceback):
        arcpy.AddMessage = OutputCapture._orig_message
        arcpy.AddWarning = OutputCapture._orig_warning
        arcpy.AddError = OutputCapture._orig_error

    def _message(self, message: str, *args: Any, **kwds: Any) -> Any:
        self.logger.debug(message.strip("\n"))  # densify
        # OutputCapture._orig_message(message) # suppress messages

    def _warning(self, message: str, *args: Any, **kwds: Any) -> Any:
        self.logger.warning(message.strip("\n"))  # densify
        # OutputCapture._orig_warning(message) # suppress messages

    def _error(self, message: str, *args: Any, **kwds: Any) -> Any:
        self.logger.error(message.strip("\n"))  # densify
        OutputCapture._orig_error(message)


def setup_logger(
    logger: logging.Logger, log_file: Union[Path, str], add_timestamp: bool = True
) -> logging.Logger:
    """Configures the logger passed and returns it. Does not create new loggers.
    Python logging module loggers are singletons based on the logger's "name".
    """

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s:%(levelname)5s: %(message)s", datefmt=PSEUDO_ISO_FMT)

    log_file = Path(log_file)
    log_file.parent.mkdir(exist_ok=True, parents=True)
    if add_timestamp:
        datetag = f"_{dt.now():{EXTRA_PSEUDO_ISO_FMT}}"
        log_file = log_file.with_stem(log_file.stem + datetag)
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    sh = logging.StreamHandler(stream=real_stdout)  # anti-kibana measure
    sh.setFormatter(formatter)
    sh.setLevel(logging.INFO)
    logger.addHandler(sh)

    return logger
