/* Auto-cierre de avisos-flash transitorios (los <p class="error"/"ok"> marcados con .autohide).
 * Tras ~6 s el aviso se desvanece y se elimina. Solo aplica a los mensajes de feedback puntual
 * (p. ej. "Corrección registrada", "esa acción no es válida…"); NUNCA a banners persistentes o
 * con acción (discrepancia, pendiente de sincronizar, PIN de un solo uso…), que no llevan la
 * clase. Re-arma tras cada swap de htmx (los fragmentos #estado / #registros se sustituyen).
 * Sin JS igualmente todo funciona: el aviso simplemente no se auto-cerraría. */
(function () {
  "use strict";
  var DELAY = 6000, FADE = 400;

  function arm(root) {
    var nodes = (root || document).querySelectorAll(".autohide");
    Array.prototype.forEach.call(nodes, function (el) {
      if (el.dataset.autohideArmed) return;
      el.dataset.autohideArmed = "1";
      setTimeout(function () {
        el.classList.add("autohide-out");
        setTimeout(function () { if (el.parentNode) el.remove(); }, FADE);
      }, DELAY);
    });
  }

  document.addEventListener("DOMContentLoaded", function () { arm(document); });
  // htmx sustituye fragmentos (#estado, #registros): re-armar en el nodo recién insertado.
  document.addEventListener("htmx:afterSwap", function (e) { arm(e.target); });
})();
