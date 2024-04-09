import binascii
import re
import base64

from typing import Tuple, Optional
from anchorpy import Program, Event

DRIFT_PROGRAM_ID: str = "dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH"
DRIFT_PROGRAM_START: str = f"Program {DRIFT_PROGRAM_ID} invoke"
PROGRAM_LOG: str = "Program log: "
PROGRAM_DATA: str = "Program data: "
PROGRAM_LOG_START_INDEX: int = len(PROGRAM_LOG)
PROGRAM_DATA_START_INDEX: int = len(PROGRAM_DATA)


class ExecutionContext:
    def __init__(self):
        self.stack: list[str] = []

    def program(self):
        if len(self.stack) == 0:
            raise ValueError("Expected the stack to have elements")
        return self.stack[-1]

    def push(self, program: str):
        self.stack.append(program)

    def pop(self):
        if len(self.stack) == 0:
            raise ValueError("Expected the stack to have elements")
        return self.stack.pop()


def parse_logs(program: Program, logs: list[str]) -> list[Event]:
    events = []
    execution = ExecutionContext()
    for log in logs:
        if log.startswith("Log truncated"):
            break

        event, new_program, did_pop = handle_log(execution, log, program)
        if event:
            events.append(event)
        if new_program:
            execution.push(new_program)
        if did_pop:
            execution.pop()

    return events


def handle_log(
    execution: ExecutionContext, log: str, program: Program
) -> Tuple[Optional[Event], Optional[str], bool]:
    if len(execution.stack) > 0 and execution.program() == DRIFT_PROGRAM_ID:
        return handle_program_log(log, program)
    else:
        return (None, *handle_system_log(log))


def handle_program_log(
    log: str, program: Program
) -> Tuple[Optional[Event], Optional[str], bool]:
    if log.startswith(PROGRAM_LOG) or log.startswith(PROGRAM_DATA):
        log_str = (
            log[PROGRAM_LOG_START_INDEX:]
            if log.startswith(PROGRAM_LOG)
            else log[PROGRAM_DATA_START_INDEX:]
        )
        try:
            decoded = base64.b64decode(log_str)
        except binascii.Error:
            return (None, None, False)
        if len(decoded) < 8:
            return (None, None, False)
        event = program.coder.events.parse(decoded)
        return (event, None, False)
    else:
        return (None, *handle_system_log(log))


def handle_system_log(log: str) -> Tuple[Optional[str], bool]:
    log_start = log.split(":")[0]

    if re.findall(r"Program (.*) success", log_start) != []:
        return (None, True)
    elif log_start.startswith(DRIFT_PROGRAM_START):
        return (DRIFT_PROGRAM_ID, False)
    elif "invoke" in log_start:
        return ("cpi", False)
    else:
        return (None, False)
