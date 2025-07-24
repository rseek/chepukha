/* ------- инициализация -------- */
let playerId   = localStorage.getItem("player_id") || crypto.randomUUID();
localStorage.setItem("player_id", playerId);

let playerName = localStorage.getItem("player_name");
if (!playerName) {
  playerName = prompt("Введите ваше имя")?.trim() || "Игрок";
  localStorage.setItem("player_name", playerName);
}

const TEXTS = {
  start_placeholder: "Начните писать чепуху!",
  from_player: name => `Вам листик от ${name}:`,
  hidden_placeholder: "Будет завёрнуто — следующий не увидит текст из этого поля",
  visible_placeholder: "Видимая часть — следующий увидит текст из этого поля",
  final_title: "Получилась какая-то чепуха:",
  waiting: "Ожидаем листик…",
};

const path    = window.location.pathname.split("/");
const roomId  = path[path.length - 1];
const protocol = location.protocol === "https:" ? "wss" : "ws";
const ws = new WebSocket(`${protocol}://${location.host}/ws/${roomId}/${playerId}`);

let gameStarted = localStorage.getItem("game_started") === "true";

const STORAGE_KEY_HIDDEN = "draft_hidden";
const STORAGE_KEY_VISIBLE = "draft_visible";

const playerList  = document.getElementById("players");
const startBtn    = document.getElementById("start");
const roundsSetting = document.getElementById("rounds-setting");
const form        = document.getElementById("form");
const hiddenField = document.getElementById("hidden");
const visibleField= document.getElementById("visible");
const visibleBlk  = document.getElementById("visible-block");
const waitBlk     = document.getElementById("wait");
const finalBlk    = document.getElementById("final");
const finalList   = document.getElementById("final-list");
const fromSpan    = document.getElementById("visible-from");
const sendBtn     = document.getElementById("send-btn");
const logout      = document.getElementById("logout")
let hiddenDraft   = "";
const preview     = document.getElementById("preview");
let lastVisible   = "";        // приходит от сервера

document.getElementById("copy-result").onclick = () => {
  const result = [...document.querySelectorAll("#final-list li")].map(li => li.textContent).join("\n");
  navigator.clipboard.writeText(result);
};
document.getElementById("wait").textContent = TEXTS.waiting
document.getElementById("hidden").placeholder = TEXTS.hidden_placeholder
document.getElementById("visible").placeholder = TEXTS.visible_placeholder
// document.getElementById("final").clas = TEXTS.final_title

hiddenField.value = localStorage.getItem(STORAGE_KEY_HIDDEN) || "";
visibleField.value = localStorage.getItem(STORAGE_KEY_VISIBLE) || "";

// обновление draft при вводе
hiddenField.addEventListener("input", () => {
  localStorage.setItem(STORAGE_KEY_HIDDEN, hiddenField.value);
});
visibleField.addEventListener("input", () => {
  localStorage.setItem(STORAGE_KEY_VISIBLE, visibleField.value);
});

function clearDraft() {
  hiddenField.value = "";
  visibleField.value = "";
  localStorage.removeItem(STORAGE_KEY_HIDDEN);
  localStorage.removeItem(STORAGE_KEY_VISIBLE);
}

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
  if (data.started) {
    logout.classList.add("hidden");
  }

  /* — players list — */
  if (data.players) {
    gameStarted = data.started ?? gameStarted;
    localStorage.setItem("game_started", gameStarted ? "true" : "false");

    playerList.innerHTML = "<ul>" +
      data.players.map(n => `<li>${n === playerName ? "<u>"+n+"</u>" : n}</li>`).join("") +
      "</ul>";

    const creator = data.plids ? data.plids[0] : playerId;
    if (!gameStarted && data.players.length >= 2 && creator === playerId) {
      roundsSetting.classList.remove("hidden");
      startBtn.classList.remove("hidden");
    } else {
        roundsSetting.classList.add("hidden");
        startBtn.classList.add("hidden");
    }
  }

  /* — visible — */
  if (data.visible !== undefined) {
    lastVisible = data.visible;
    fromSpan.textContent = data.from
      ? TEXTS.from_player(data.from)
      : TEXTS.start_placeholder;
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
    if (data.sheets) {
      finalList.innerHTML = data.sheets
      .map(s => `${s}`).join("");
    }
    startBtn.disabled = false;
  }
};

/* ------- buttons -------- */
startBtn.onclick = () => {
  const rounds = document.querySelector("#rounds").value;
  ws.send(JSON.stringify({ action: "start", rounds: Number(rounds)}));
  localStorage.setItem("game_started", "true");
  startBtn.disabled = true;
  logout.classList.add("hidden");
};

logout.onclick = () => {
  localStorage.removeItem("player_id");
  localStorage.removeItem("player_name");
  location.reload();
};

form.onsubmit = (e) => {
  e.preventDefault();
  const hidden = hiddenField.value.trim();
  const visible = visibleField.value.trim();
  if (!hidden && !visible) return;     // обе пустые — не шлём

  ws.send(JSON.stringify({ hidden, visible }));

  clearDraft()
  updatePreview();
  updateSendBtn();
  form.classList.add("hidden");        // ждём новую бумажку
};
