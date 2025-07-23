let gameStarted = localStorage.getItem("game_started") === "true";
let playerId = localStorage.getItem("player_id") || crypto.randomUUID();

const urlParts = window.location.pathname.split("/");
const roomId = urlParts[urlParts.length - 1];
const ws = new WebSocket(`ws://${location.host}/ws/${roomId}/${playerId}`);

const playerList = document.getElementById("players");
const startBtn = document.getElementById("start");
const form = document.getElementById("form");
const hiddenField = document.getElementById("hidden");
const visibleField = document.getElementById("visible");
const visibleBlock = document.getElementById("visible-block");
const waitBlock = document.getElementById("wait");
const finalBlock = document.getElementById("final");
const finalList = document.getElementById("final-list");
const wrapBtn      = document.getElementById("wrap-btn");
const secondStep   = document.getElementById("second-step");
let   hiddenDraft  = "";              // временно храним «скрытую» часть

localStorage.setItem("player_id", playerId);

// --- имя игрока ---
let playerName = localStorage.getItem("player_name");
if (!playerName) {
    playerName = prompt("Введите ваше имя")?.trim() || "Игрок";
    localStorage.setItem("player_name", playerName);
}

ws.addEventListener("open", () => {
    ws.send(JSON.stringify({ action: "introduce", name: playerName }));
});

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.start) {
        localStorage.setItem("game_started", "true");
    }
    gameStarted = localStorage.getItem("game_started") === "true";
    if (data.wait && gameStarted) {
        visibleBlock.classList.add("hidden");
        waitBlock.classList.remove("hidden");
        finalBlock.classList.add("hidden");
        form.classList.add("hidden");
    } else {
        waitBlock.classList.add("hidden");
    }

    if (data.players) {
        if (data.started !== undefined) {
            gameStarted = data.started;
            localStorage.setItem("game_started", gameStarted ? "true" : "false");
        }
        const plids = data.plids;
        const names = data.players;

        playerList.innerHTML =
            "<b>Игроки:</b><ul>" +
            names.map(n => `<li>${n === playerName ? "<u>"+n+"</u>" : n}</li>`).join("") +
            "</ul>";

        if (!gameStarted && !data.finished && plids[0] === playerId && plids.length >= 2) {
            startBtn.classList.remove("hidden");
        } else {
            startBtn.classList.add("hidden");
        }
    }

    if ((data.visible !== undefined) && gameStarted) {
        document.getElementById("visible-from").innerText =
          data.from ? `Чепуха от ${data.from}` : "Начните писать чепуху!";
        visibleBlock.classList.remove("hidden");
        waitBlock.classList.add("hidden");
        finalBlock.classList.add("hidden");
        form.classList.remove("hidden");
        visibleBlock.querySelector(".visible-text").innerText = data.visible;
    }

    if (data.finished) {
        localStorage.setItem("game_started", "false");
        visibleBlock.classList.add("hidden");
        waitBlock.classList.add("hidden");
        form.classList.add("hidden");
        finalBlock.classList.remove("hidden");
        finalList.innerHTML = data.sheets.map(p => `<li><pre>${p}</pre></li>`).join("");
        startBtn.disabled = false;
    }
};

startBtn.onclick = () => {
    ws.send(JSON.stringify({ action: "start" }));
    localStorage.setItem("game_started", "true");
    startBtn.disabled = true;
};

wrapBtn.onclick = () => {
  hiddenDraft = hiddenField.value.trim();
  if (!hiddenDraft) return alert("Введите скрытый текст!");

  // hiddenField.disabled = true;
  // wrapBtn.disabled     = true;

  secondStep.classList.remove("hidden");          // показываем 2‑й этап
  visibleField.focus();
};

form.onsubmit = (e) => {
  e.preventDefault();
  const visible = visibleField.value.trim();
  if (!hiddenDraft || !visible) return;

  ws.send(JSON.stringify({ hidden: hiddenDraft, visible }));

  // сбросить UI в исходное состояние
  hiddenDraft = "";
  hiddenField.value = visibleField.value = "";
  hiddenField.disabled = false;
  wrapBtn.disabled     = false;
  secondStep.classList.add("hidden");
};
