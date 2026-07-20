"""Shared pytest fixtures: an isolated in-memory DB per test, wired into the app."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db import get_db, init_db
from app.main import app


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def client(conn):
    def override_get_db():
        yield conn

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
