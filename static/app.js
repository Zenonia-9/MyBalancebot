const tg = window.Telegram.WebApp;
tg.expand();

// 🔥 REAL USER ID from Telegram
const user = tg.initDataUnsafe?.user;
const user_id = user?.id;

// fallback for local testing
const fallback_id = 1;

function getUserId() {
  return user_id || fallback_id;
}

function loadBalance() {
  fetch(`/api/balance?user_id=${getUserId()}`)
    .then(res => res.json())
    .then(data => {
      document.getElementById("balance").innerText =
        data.balance + " MMK";
    });
}

function add() {
  const amount = document.getElementById("amount").value;
  const note = document.getElementById("note").value;

  fetch("/api/add", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      user_id: getUserId(),
      amount: amount,
      note: note
    })
  }).then(() => loadBalance());
}

loadBalance();