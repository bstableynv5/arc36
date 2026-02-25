PSEUDO_ISO_FMT = "%Y-%m-%d %H:%M:%S"
"""Y-m-d H:M:S"""
EXTRA_PSEUDO_ISO_FMT = "%Y%m%d%H%M%S"
"""YmdHMS"""


def single_test_logfile(run_id: int, env: str, test_id: str) -> str:
    """Format the filename for an single tool test's log."""
    return f"{run_id:03d}_{env}_{test_id}.log"


def single_test_inputs(env: str, test_id: str) -> str:
    """Format the temp input dir for a single tool test."""
    return f"inputs_{env}_{test_id}"


def single_test_outputs(env: str, test_id: str) -> str:
    """Format the output dir for a single tool test."""
    return f"outputs_{env}_{test_id}"


def run_logfile(run_id: int, env: str) -> str:
    """Format the filename for a run's log."""
    return f"{run_id:03d}_{env}.log"
