from fastapi import APIRouter, WebSocket
from fastapi.responses import HTMLResponse
from game import manager

router = APIRouter()

@router.get("/room/{room_id}")
async def get_room(room_id: str, theme: str = "light"):
    filename = "static/room_dark.html" if theme == "dark" else "static/room.html"
    with open(filename, encoding="utf-8") as f:
        return HTMLResponse(f.read())

@router.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    await manager.connect(room_id, player_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_input(room_id, player_id, data)
    except Exception as e:
        print(f"[WS ERROR] {e}")
        print(locals())
    finally:
        await manager.disconnect(room_id, player_id)
