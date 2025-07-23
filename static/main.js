const playerId = localStorage.getItem("player_id") || crypto.randomUUID();
localStorage.setItem("player_id", playerId);

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
let gameStarted = localStorage.getItem("game_started") === "true";

localStorage.setItem("game_started", "false");
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(localStorage.getItem("game_started"))

    if (data.start) {
        console.log("ALAL data.start")
        gameStarted = true;
        localStorage.setItem("game_started", "true");
    }

    if (data.wait && gameStarted) {
        visibleBlock.classList.add("hidden");
        waitBlock.classList.remove("hidden");
        finalBlock.classList.add("hidden");
        form.classList.add("hidden");
    } else {
        waitBlock.classList.add("hidden");
    }

    if (data.players) {
        const players = data.players;
        playerList.innerHTML = "<b>Игроки:</b> " + players.map(p => p === playerId ? `<u>${p}</u>` : p).join(", ");

        // Показываем кнопку "Начать", если:
        // - текущий игрок — первый (creator)
        // - и игроков двое или больше
        if (players[0] === playerId && players.length >= 2) {
            startBtn.classList.remove("hidden");
        } else {
            startBtn.classList.add("hidden");
        }
    }

    if (data.visible !== undefined) {
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
    }
};

startBtn.onclick = () => {
    ws.send(JSON.stringify({ action: "start" }));
    localStorage.setItem("game_started", "true");
    startBtn.disabled = true;
};

form.onsubmit = (e) => {
    e.preventDefault();
    const hidden = hiddenField.value.trim();
    const visible = visibleField.value.trim();
    if (!hidden && !visible) return;
    ws.send(JSON.stringify({ hidden, visible }));
    hiddenField.value = "";
    visibleField.value = "";
};
