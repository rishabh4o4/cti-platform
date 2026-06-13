import pytest
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect

from app.main import app
from app.services.websocket import manager
from app.core.config import settings
from app.core.security import create_access_token

def test_websocket_unauthenticated_rejected():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/v1/alerts/ws"):
                pass
        assert exc.value.code == 4001

def test_websocket_invalid_token_rejected():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/v1/alerts/ws?token=invalid_token"):
                pass
        assert exc.value.code == 4001

def test_websocket_max_connections():
    # Setup the manager with active_connections already at max
    original_connections = manager.active_connections.copy()
    try:
        manager.active_connections = [None] * settings.ws_max_connections
        
        token = create_access_token(subject="testuser")
        
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc:
                with client.websocket_connect(f"/api/v1/alerts/ws?token={token}"):
                    pass
            assert exc.value.code == 1008
    finally:
        manager.active_connections = original_connections
