from __future__ import annotations

import os
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import dict_row


@lru_cache(maxsize=1)
def get_postgres_checkpointer() -> PostgresSaver:
    database_url = os.getenv("LANGGRAPH_CHECKPOINT_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "Missing required environment variable: "
            "LANGGRAPH_CHECKPOINT_DATABASE_URL"
        )

    connection = Connection.connect(
        database_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )

    checkpointer = PostgresSaver(connection)
    checkpointer.setup()

    return checkpointer