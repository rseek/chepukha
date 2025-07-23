from dataclasses import dataclass, field
from typing import List, Optional
import asyncio

@dataclass
class Step:
    hidden: str
    visible: str

    def to_text(self):
        return f"{self.hidden}\n{self.visible}"

@dataclass
class Player:
    id: str
    ws: any
    sheet: List[Step] = field(default_factory=list)
    queue: List[str] = field(default_factory=list)
    current_round: int = 0

@dataclass
class Room:
    id: str
    players: List[Player] = field(default_factory=list)
    started: bool = False

    def get_player_by_id(self, pid: str) -> Optional[Player]:
        return next((p for p in self.players if p.id == pid), None)

    def get_next_player(self, current_index: int) -> Player:
        return self.players[(current_index + 1) % len(self.players)]

    def all_finished(self) -> bool:
        total_rounds = len(self.players) * 3
        return all(p.current_round >= 3 for p in self.players)

class GameManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}

    async def connect(self, room_id: str, player_id: str, websocket):
        await websocket.accept()
        room = self.rooms.setdefault(room_id, Room(id=room_id))
        existing = room.get_player_by_id(player_id)
        if existing:
            existing.ws = websocket
        else:
            room.players.append(Player(id=player_id, ws=websocket))
        print(f"[CONNECT] {player_id} подключился к комнате {room_id}")
        await self.broadcast_players(room_id)

    async def disconnect(self, room_id: str, player_id: str):
        room = self.rooms.get(room_id)
        if room:
            room.players = [p for p in room.players if p.id != player_id]
            print(f"[DISCONNECT] {player_id} покинул комнату {room_id}")

    async def handle_input(self, room_id: str, player_id: str, data: dict):
        room = self.rooms.get(room_id)
        if not room:
            return

        if data.get("action") == "start":
            if not room.started and room.players and room.players[0].id == player_id and len(room.players) >= 2:
                room.started = True
                for p in room.players:
                    p.queue = ["(первая строка)"]
                print(f"[GAME START] Комната {room_id} — игра началась")
                await self.dispatch_turns(room)
            return

        if not room.started:
            return

        sender = room.get_player_by_id(player_id)
        if not sender or not sender.queue:
            return

        hidden = data.get("hidden", "")
        visible = data.get("visible", "")
        print(f"[INPUT] {player_id} → скрыто: '{hidden}', видно: '{visible}'")

        sender.sheet.append(Step(hidden, visible))
        sender.current_round += 1
        sender.queue.pop(0)

        sender_idx = room.players.index(sender)
        next_player = room.get_next_player(sender_idx)
        next_player.queue.append(visible)

        await self.dispatch_turns(room)

        if room.all_finished():
            print(f"[COMPLETE] Комната {room_id} завершена")
            sheets = ["\n".join(step.to_text() for step in p.sheet) for p in room.players]
            for p in room.players:
                await p.ws.send_json({"finished": True, "sheets": sheets})
            room.started = False

    async def dispatch_turns(self, room: Room):
        for p in room.players:
            if p.queue:
                await p.ws.send_json({"visible": p.queue[0]})
            else:
                await p.ws.send_json({"wait": True})

    async def broadcast_players(self, room_id: str):
        room = self.rooms.get(room_id)
        if not room:
            return
        ids = [p.id for p in room.players]
        for p in room.players:
            await p.ws.send_json({"players": ids})

manager = GameManager()
