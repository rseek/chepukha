from __future__ import annotations
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from fastapi import WebSocket
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

BASE_STORAGE_DIR = "chepukha_storage"
load_dotenv()

# ──────────────────────────── models ────────────────────────────
@dataclass
class Step:
    hidden: str
    visible: str
    author: str

    def to_text(self) -> str:
        return f"{self.hidden}\n{self.visible}"


@dataclass
class Player:
    id: str
    ws: WebSocket
    name: str = "Игрок"
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
        self.session_time: str = "not_started"

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
            player = Player(player_id, ws=ws)
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
        """Отправляем всем актуальный список имён + статусы.
           Сокеты, которые уже закрылись, удаляем из комнаты."""
        ids   = [p.id   for p in room.players]
        names = [p.name for p in room.players]

        dead = []                                 # сюда соберём мертвых

        for p in room.players:
            payload = {
                "plids":   ids,                   # порядок id (для кнопки «Начать»)
                "players": names,                 # имена
                "started": room.started,
                "finished": p.finished,
            }
            try:
                await self.safe_send(p, payload)
            except RuntimeError:
                # сокет уже закрыт (старый вкладка / тайм‑аут)
                dead.append(p)

        # убираем мертвецов из комнаты
        if dead:
            for p in dead:
                room.players.remove(p)
                print(f"[CLEANUP] drop closed ws of {p.id}")

    async def safe_send(self, player: Player, payload: dict):
        try:
            await player.ws.send_json(payload)
        except RuntimeError:
            print(f"[DROP] ws of {player.id} closed")

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
            await self.safe_send(player,{"wait": True})
            return

        sheet_idx = player.inbox[0]

        # если лист ещё не создан (может быть на ранней стадии игры)
        if sheet_idx >= len(room.sheets):
            await self.safe_send(player, {"visible": "", "from": None})
            return

        sheet = room.sheets[sheet_idx]
        if sheet:
            visible = sheet[-1].visible
            await self.safe_send(player, {"visible": visible, "from": sheet[-1].author})
        else:
            # лист пустой — первая строка
            await self.safe_send(player, {"visible": "", "from": None})
        try:
            last = room.sheets[sheet_idx][-1]
            await self.safe_send(player, {
                "visible": last.visible,
                "from":    last.author
            })
        except IndexError as ie:
            await self.safe_send(player, {"visible": "", "from": None})

    # ── game flow ────────────────────────────────────────────────
    async def handle_input(self, room_id: str, pid: str, data: dict):
        room = self.rooms.get(room_id)
        if not room:
            return

        # игрок прислал своё имя
        if data.get("action") == "introduce":
            player = room.get_player_by_id(pid)
            if player and isinstance(data.get("name"), str):
                player.name = data["name"][:40]            # ограничим длину
                await self.broadcast_players(room)
            return

        # ─ start ─
        if data.get("action") == "start":
            if (not room.started
                    and room.players
                    and len(room.players) >= 2
                    and room.players[0].id == pid):
                room.session_time = datetime.now().strftime("%Y%m%d%H%M%S")
                room.storage_path = os.path.join(BASE_STORAGE_DIR, room_id, room.session_time)
                os.makedirs(room.storage_path, exist_ok=True)
                room.started = True
                room.finised = False
                room.rounds_total = int(data.get("rounds", 1))  # по умолчанию 1
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
        room.sheets[sheet_idx].append(Step(hidden, visible, author=player.name))
        # если этот лист — «домашний» и он полный → игрок закончил
        if (sheet_idx == player.home_sheet
                and len(room.sheets[sheet_idx]) - 1 == room.rounds_total * len(room.players)):
            player.finished = True
            player.inbox.clear()
            await self.safe_send(player, {
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

        for i, sheet in enumerate(room.sheets):
            path = os.path.join(room.storage_path, f"{room.players[i].name}.txt")
            content = "\n".join(line.hidden + "\n" + line.visible for line in sheet)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            if os.getenv("PUSH_TO_S3") == "YES":
                upload_to_s3(room_id, room.session_time, room.players[i].name, content)


# экземпляр менеджера
manager = GameManager()

if os.getenv("PUSH_TO_S3") == "YES":
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url=os.getenv("S3_ENDPOINT"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY")
    )

def upload_to_s3(room_id, session_time, player_name, content):
    key = f"{room_id}/{session_time}/{player_name}.txt"
    try:
        s3.put_object(
            Bucket=os.getenv("S3_BUCKET"),
            Key=key,
            Body=content.encode('utf-8')
        )
    except ClientError as e:
        print("S3 Upload error:", e)
