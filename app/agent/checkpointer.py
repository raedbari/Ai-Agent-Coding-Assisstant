from __future__ import annotations

import os
from functools import lru_cache
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver


@lru_cache(maxsize=1)
def get_postgres_checkpointer():
    database_url = os.getenv("LANGGRAPH_CHECKPOINT_DATABASE_URL")

    if not database_url:
        raise RuntimeError("Missing LANGGRAPH_CHECKPOINT_DATABASE_URL")

    # PostgresSaver is a context manager in your version
    return PostgresSaver.from_conn_string(database_url)


@contextmanager
def get_checkpointer_context():
    cp = get_postgres_checkpointer()
    with cp as checkpointer:
        yield checkpointer