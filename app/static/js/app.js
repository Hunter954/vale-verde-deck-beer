document.addEventListener("click", async (e) => {
  const groupBtn = e.target.closest(".js-kds-order-status");
  if (groupBtn) {
    const card = groupBtn.closest(".kds-order-card");
    const page = document.querySelector("#kds-page");
    if (!card) return;
    groupBtn.disabled = true;
    const res = await fetch("/kds/api/order-status", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        order_id: card.dataset.orderId,
        current_status: card.dataset.status,
        status: groupBtn.dataset.status,
        sector: page?.dataset.sector || "cozinha"
      })
    });
    if (res.ok) window.location.reload();
    else groupBtn.disabled = false;
    return;
  }

  const deliverAll = e.target.closest(".js-kds-deliver-all");
  if (deliverAll) {
    const page = document.querySelector("#kds-page");
    deliverAll.disabled = true;
    const res = await fetch("/kds/api/mark-ready-delivered", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({sector: page?.dataset.sector || "cozinha"})
    });
    if (res.ok) window.location.reload();
    else deliverAll.disabled = false;
    return;
  }

  const btn = e.target.closest(".js-status");
  if (!btn) return;
  const card = btn.closest(".kds-card");
  const id = card?.dataset.id;
  const status = btn.dataset.status;
  const res = await fetch(`/kds/api/items/${id}/status`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({status})
  });
  if (res.ok) {
    card.querySelectorAll(".js-status").forEach(b => b.classList.remove("btn-neon"));
    btn.classList.add("btn-neon");
    if (status === "Pronto") card.style.borderColor = "rgba(57,255,136,.7)";
  }
});

function refreshKDSTimers(){
  const page = document.querySelector("#kds-page");
  if(!page) return;
  document.querySelectorAll(".kds-timer").forEach(timer => {
    const text = timer.textContent.trim().match(/(\d+):(\d+)/);
    if(!text) return;
    let minutes = parseInt(text[1], 10);
    let seconds = parseInt(text[2], 10) + 1;
    if(seconds >= 60){ minutes += 1; seconds = 0; }
    const formatted = `${String(minutes).padStart(2,"0")}:${String(seconds).padStart(2,"0")}`;
    timer.innerHTML = `<i class="bi bi-clock"></i> ${formatted}`;
    timer.classList.toggle("danger", minutes >= 15);
    timer.classList.toggle("warn", minutes >= 8 && minutes < 15);
    timer.classList.toggle("ok", minutes < 8);
  });
}
setInterval(refreshKDSTimers, 1000);
if (document.querySelector("#kds-page")) {
  setInterval(() => window.location.reload(), 30000);
}

function formatBRMoneyFromDigits(raw) {
  const digits = String(raw || "").replace(/\D/g, "");
  if (!digits) return "R$ 0,00";
  const value = Number(digits) / 100;
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function setupMoneyInputs() {
  document.querySelectorAll(".js-money-input").forEach((input) => {
    if (input.dataset.moneyReady === "1") return;
    input.dataset.moneyReady = "1";

    const applyMask = () => {
      input.value = formatBRMoneyFromDigits(input.value);
    };

    input.addEventListener("input", applyMask);
    input.addEventListener("focus", () => input.select());
    input.addEventListener("blur", applyMask);

    if (input.value && !input.value.trim().startsWith("R$")) {
      const hasDecimal = /[,.]/.test(input.value);
      if (hasDecimal) {
        const numeric = Number(String(input.value).replace(/\./g, "").replace(",", "."));
        input.value = Number.isFinite(numeric)
          ? numeric.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
          : formatBRMoneyFromDigits(input.value);
      } else {
        applyMask();
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", setupMoneyInputs);
