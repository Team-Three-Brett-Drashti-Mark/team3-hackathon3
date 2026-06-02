import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

_executor = ThreadPoolExecutor(max_workers=2)
_logger = logging.getLogger("pathwise.logger")

_INSERT_SQL = """
INSERT INTO capstone.logging.interaction_logs
  (log_id, session_id, timestamp, user_input, system_output,
   intent, attempt, input_length_chars, response_length_chars)
VALUES
  ('{log_id}', '{session_id}', '{timestamp}', '{user_input}',
   '{system_output}', '{intent}', {attempt},
   {input_length_chars}, {response_length_chars})
"""

_FALLBACK_PATH = "app.log"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _write_to_delta(session_id: str, user_input: str, system_output: str,
                    intent: str, attempt: int) -> None:
    try:
        # auth_type="pat" is REQUIRED in the Databricks App runtime: it injects
        # both a PAT (DATABRICKS_TOKEN) and the app SP's OAuth creds
        # (DATABRICKS_CLIENT_ID/SECRET), and without pinning one the SDK raises
        # "validate: more than one authorization method configured: oauth and
        # pat" — which made every Delta log write fail and silently fall back to
        # app.log, so nothing landed in interaction_logs. Matches app/admin.py.
        client = WorkspaceClient(
            host=os.environ["DATABRICKS_HOST"],
            token=os.environ["DATABRICKS_TOKEN"],
            auth_type="pat",
        )
        sql = _INSERT_SQL.format(
            log_id=str(uuid.uuid4()),
            session_id=_escape(session_id),
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            user_input=_escape(user_input),
            system_output=_escape(system_output),
            intent=_escape(intent),
            attempt=attempt,
            input_length_chars=len(user_input),
            response_length_chars=len(system_output),
        )
        response = client.statement_execution.execute_statement(
            warehouse_id=_get_warehouse_id(client),
            statement=sql,
            catalog="capstone",
            schema="logging",
            wait_timeout="10s",
        )
        state = response.status.state if response.status else None
        if state != StatementState.SUCCEEDED:
            raise RuntimeError(f"Statement state: {state}")
    except Exception as exc:  # noqa: BLE001
        _fallback_log(session_id, user_input, system_output, intent, attempt, str(exc))


def _get_warehouse_id(client: WorkspaceClient) -> str:
    warehouses = list(client.warehouses.list())
    if not warehouses or warehouses[0].id is None:
        raise RuntimeError("No SQL warehouses available")
    return warehouses[0].id


def _fallback_log(session_id: str, user_input: str, system_output: str,
                  intent: str, attempt: int, error: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    message = (
        f"[{timestamp}] [DELTA_FAIL: {error}]\n"
        f"SESSION: {session_id}\n"
        f"USER INPUT: {user_input}\n"
        f"SYSTEM OUTPUT: {system_output}\n"
        f"INTENT: {intent}\n"
        f"ATTEMPT: {attempt}\n"
        + "-" * 50
    )
    _logger.warning(message)
    with open(_FALLBACK_PATH, "a") as f:
        f.write(message + "\n")


def log_interaction(session_id: str, user_input: str, system_output: str,
                    intent: str, attempt: int) -> None:
    """Fire-and-forget: submits the DB write to a background thread so it never
    blocks the /chat response. Falls back to app.log if the Delta write fails."""
    _executor.submit(
        _write_to_delta, session_id, user_input, system_output, intent, attempt
    )
