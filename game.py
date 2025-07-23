from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from fastapi import WebSocket


# ──────────────────────────── models ────────────────────────────
@dataclass
class Step:
    hidden: str
    visible: str

    def to_text(self) -> str:
        return f"{self.hidden}\n{self.visible}"


@dataclass
class Player:
    id: str
    ws: WebSocket
    inbox: list[int] = field(default_factory=list)   # индексы листиков, которые лежат «у меня»
    current_round: int = 0
    home_sheet: int = -1          # индекс «родного» листа
    finished: bool = False


class Room:
    def __init__(self, rounds_total: int = 1):
        self.rounds_total = rounds_total
        self.players: list[Player] = []
        self.sheets: list[list[Step]] = []           # все листики
        self.started: bool = False
        self.finished: bool = False

    # helpers
    def get_player_by_id(self, pid: str) -> Optional[Player]:
        return next((p for p in self.players if p.id == pid), None)

    def next_player(self, idx: int) -> Player:
        return self.players[(idx + 1) % len(self.players)]

    def all_finished(self) -> bool:
        target = self.rounds_total
        return all(len(sheet) == target for sheet in self.sheets)


# ──────────────────────── game‑manager ──────────────────────────
class GameManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    # ── connection ───────────────────────────────────────────────
    async def connect(self, room_id: str, player_id: str, ws: WebSocket):
        await ws.accept()
        room = self.rooms.setdefault(room_id, Room())

        player = room.get_player_by_id(player_id)
        if player:                                 # reconnect
            player.ws = ws
            print(f"[RECONNECT] {player_id} -> {room_id}")
        else:                                      # new player
            player = Player(player_id, ws)
            room.players.append(player)
            print(f"[CONNECT]   {player_id} -> {room_id}")

        await self.broadcast_players(room)

        # вернуть результат, если уже finished
        if player.finished:
            idx = player.home_sheet
            sheet_txt = "\n".join(step.to_text() for step in room.sheets[idx])
            await ws.send_json({"players": [p.id for p in room.players], "finished": True, "sheets": [sheet_txt]})
            return

        # вернуть состояние, если игра уже идёт
        if room.started:
            await self.deliver_state(room, player)

    async def disconnect(self, room_id: str, player_id: str):
        room = self.rooms.get(room_id)
        if room:
            print(f"[DISCONNECT] {player_id} из {room_id} (игрок остаётся в памяти)")

    # ── helpers ──────────────────────────────────────────────────
    async def broadcast_players(self, room: Room):
        ids = [p.id for p in room.players]
        for p in room.players:
            if p.finished:
                print("player finished")
            else:
                print("player NOT finished")
                await p.ws.send_json({"players": ids, "started": room.started, "finished": room.finished})

    async def deliver_state(self, room: Room, player: Player):
        """
        Отсылает игроку либо последнюю видимую строку,
        либо 'wait', если листика нет.
        Работает безопасно даже до старта игры или
        если inbox указывает на несуществующий лист.
        """
        # нет листиков у игрока → ждём
        if player.finished:
            return  # больше ничего не шлём, он уже вышел из игры
        if not player.inbox:
            await player.ws.send_json({"wait": True})
            return

        sheet_idx = player.inbox[0]

        # если лист ещё не создан (может быть на ранней стадии игры)
        if sheet_idx >= len(room.sheets):
            await player.ws.send_json({"visible": "(первая строка)"})
            return

        sheet = room.sheets[sheet_idx]
        if sheet:
            visible = sheet[-1].visible
            await player.ws.send_json({"visible": visible})
        else:
            # лист пустой — первая строка
            await player.ws.send_json({"visible": "(первая строка)"})

    # ── game flow ────────────────────────────────────────────────
    async def handle_input(self, room_id: str, pid: str, data: dict):
        room = self.rooms.get(room_id)
        if not room:
            return

        # ─ start ─
        if data.get("action") == "start":
            if (not room.started
                    and room.players
                    and len(room.players) >= 2
                    and room.players[0].id == pid):
                room.started = True
                room.finised = False
                room.sheets = [[] for _ in room.players]
                for idx, p in enumerate(room.players):
                    p.inbox = [idx]               # у каждого свой листик
                    p.current_round = 0
                    p.home_sheet = idx            # ← запомнили
                    p.finished = False
                await self.broadcast_players(room)
                for p in room.players:
                    await self.deliver_state(room, p)
                print(f"[START] room {room_id}")
            return

        if not room.started:
            return

        # ─ ход ─
        player = room.get_player_by_id(pid)
        if not player or not player.inbox:
            return

        hidden, visible = data.get("hidden", ""), data.get("visible", "")
        sheet_idx = player.inbox.pop(0)           # берём свой лист
        room.sheets[sheet_idx].append(Step(hidden, visible))
        # если этот лист — «домашний» и он полный → игрок закончил
        if (sheet_idx == player.home_sheet
                and len(room.sheets[sheet_idx]) - 1 == room.rounds_total * len(room.players)):
            player.finished = True
            player.inbox.clear()
            await player.ws.send_json({
                "finished": True,
                "sheets": ["\n".join(step.to_text() for step in room.sheets[sheet_idx])]
            })
        else:
            player.current_round += 1

            # передаём лист следующему
            next_p = room.next_player(room.players.index(player))
            next_p.inbox.append(sheet_idx)

            # раздаём состояние обоим
            await self.deliver_state(room, next_p)
            await self.deliver_state(room, player)

# экземпляр менеджера
manager = GameManager()
