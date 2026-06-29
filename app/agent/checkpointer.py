from __future__ import annotations

import os
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver


@lru_cache(maxsize=1)
def get_postgres_checkpointer() -> PostgresSaver:
    database_url = os.getenv("LANGGRAPH_CHECKPOINT_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "Missing required environment variable: "
            "LANGGRAPH_CHECKPOINT_DATABASE_URL"
        )

    checkpointer = PostgresSaver.from_conn_string(database_url)

    # Required the first time. Safe to call on startup for MVP.
    checkpointer.setup()

    return checkpointer