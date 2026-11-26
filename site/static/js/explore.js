// Explore page: the claim cards are already in the HTML (so the page works
// without JavaScript too). Here we only hide the cards that don't match.
(function () {
  "use strict";
  const cards = document.querySelectorAll(".claim-card");
  const empty = document.getElementById("empty");

  Atlas.onChange((matched) => {
    const ids = new Set(matched.map((c) => c.id));
    cards.forEach((card) => { card.hidden = !ids.has(card.dataset.id); });
    empty.hidden = ids.size > 0;
  });
  Atlas.start();
})();
