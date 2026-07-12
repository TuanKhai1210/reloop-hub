from fastapi import WebSocket


class HubConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        disconnected: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except RuntimeError:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


hub_manager = HubConnectionManager()
