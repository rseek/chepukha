/* ------- инициализация -------- */
let playerId   = localStorage.getItem("player_id") || crypto.randomUUID();
localStorage.setItem("player_id", playerId);

let playerName = localStorage.getItem("player_name");
if (!playerName) {
  playerName = prompt("Введите ваше имя")?.trim() || "Игрок";
  localStorage.setItem("player_name", playerName);
}

const path    = window.location.pathname.split("/");
const roomId  = path[path.length - 1];
const ws      = new WebSocket(`ws://${location.host}/ws/${roomId}/${playerId}`);

let gameStarted = localStorage.getItem("game_started") === "true";

/* ------- DOM --------- */
const playerList  = document.getElementById("players");
const startBtn    = document.getElementById("start");
const form        = document.getElementById("form");
const hiddenField = document.getElementById("hidden");
const visibleField= document.getElementById("visible");
const visibleBlk  = document.getElementById("visible-block");
const waitBlk     = document.getElementById("wait");
const finalBlk    = document.getElementById("final");
const finalList   = document.getElementById("final-list");
const fromSpan    = document.getElementById("visible-from");

const sendBtn = document.getElementById("send-btn");

let hiddenDraft = "";

/* ---------- валидация & превью ---------- */
const preview = document.getElementById("preview");
let lastVisible = "";        // приходит от сервера

function updateSendBtn() {
  const ok = hiddenField.value.trim() || visibleField.value.trim();
  sendBtn.disabled = !ok;
}
function updatePreview() {
  preview.textContent =
    [lastVisible, hiddenField.value, visibleField.value]
      .filter(Boolean).join("\n");
}

hiddenField.addEventListener("input", () => { updateSendBtn(); updatePreview(); });
visibleField.addEventListener("input", () => { updateSendBtn(); updatePreview(); });

/* ------- WS open -------- */
ws.addEventListener("open", () => {
  ws.send(JSON.stringify({ action: "introduce", name: playerName }));
});

/* ------- WS message ------- */
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);

  /* — players list — */
  if (data.players) {
    gameStarted = data.started ?? gameStarted;
    localStorage.setItem("game_started", gameStarted ? "true" : "false");

    playerList.innerHTML = "<ul>" +
      data.players.map(n => `<li>${n === playerName ? "<u>"+n+"</u>" : n}</li>`).join("") +
      "</ul>";

    const creator = data.plids ? data.plids[0] : playerId;
    if (!gameStarted && data.players.length >= 2 && creator === playerId) {
      startBtn.classList.remove("hidden");
    } else startBtn.classList.add("hidden");
  }

  /* — visible — */
  if (data.visible !== undefined) {
    lastVisible = data.visible;
    fromSpan.textContent = data.from
      ? `Чепуха от ${data.from}:`
      : "Начните писать чепуху!";
    visibleBlk.classList.remove("hidden");
    visibleBlk.querySelector(".visible-text").textContent = data.visible;

    waitBlk.classList.add("hidden");
    finalBlk.classList.add("hidden");
    form.classList.remove("hidden");

    updatePreview();          // показать в правом блоке
    updateSendBtn();    
  }

  /* — wait — */
  if (data.wait && gameStarted) {
    waitBlk.classList.remove("hidden");
    form.classList.add("hidden");
    visibleBlk.classList.add("hidden");
  }

  /* — finished — */
  if (data.finished) {
    localStorage.setItem("game_started", "false");
    form.classList.add("hidden");
    waitBlk.classList.add("hidden");
    visibleBlk.classList.add("hidden");
    finalBlk.classList.remove("hidden");
    finalList.innerHTML = data.sheets
      .map(s => `<li><pre>${s}</pre></li>`).join("");
    startBtn.disabled = false;
  }
};

/* ------- buttons -------- */
startBtn.onclick = () => {
  ws.send(JSON.stringify({ action: "start" }));
  localStorage.setItem("game_started", "true");
  startBtn.disabled = true;
};

form.onsubmit = (e) => {
  e.preventDefault();
  const hidden = hiddenField.value.trim();
  const visible = visibleField.value.trim();
  if (!hidden && !visible) return;     // обе пустые — не шлём

  ws.send(JSON.stringify({ hidden, visible }));

  /* reset только своих полей */
  hiddenField.value = visibleField.value = "";
  updatePreview();
  updateSendBtn();
  form.classList.add("hidden");        // ждём новую бумажку
};
