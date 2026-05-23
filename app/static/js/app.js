document.addEventListener("click", async (e) => {
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

async function refreshKDS(){
  const board = document.querySelector("#kds-board");
  if(!board) return;
  const sector = board.dataset.sector || "cozinha";
  const res = await fetch(`/kds/api/items?sector=${sector}`);
  if(!res.ok) return;
  const items = await res.json();
  board.innerHTML = items.map(i => `
    <div class="kds-card" data-id="${i.id}">
      <div class="d-flex justify-content-between"><strong>${i.table}</strong><span>${i.created_at}</span></div>
      <h4>${i.quantity}x ${i.product}</h4>
      <p>${i.note || "Sem observação"}</p>
      <div class="btn-group w-100">
        ${["Pendente","Em preparo","Pronto"].map(st => `<button class="btn btn-sm ${i.status===st?'btn-neon':'btn-outline-light'} js-status" data-status="${st}">${st}</button>`).join("")}
      </div>
    </div>`).join("");
}
setInterval(refreshKDS, 12000);
