(function () {
  var deck = document.getElementById('hotels');
  if (!deck) return;

  var raf = 0;
  var lastSelected = null;

  function mobile() {
    return window.matchMedia &&
      window.matchMedia('(max-width: 639px)').matches;
  }

  function cardList() {
    return [].slice.call(deck.querySelectorAll('.hcard'));
  }

  function selectedCard() {
    var row = deck.querySelector('.row.on');
    return row ? row.closest('.hcard') : null;
  }

  function updateFocus() {
    var cards = cardList();
    if (!cards.length) return;

    if (!mobile()) {
      cards.forEach(function (card) {
        card.classList.remove('focus');
      });
      return;
    }

    var r = deck.getBoundingClientRect();
    var center = r.left + r.width / 2;
    var best = cards[0];
    var bestDistance = Infinity;

    cards.forEach(function (card) {
      var cr = card.getBoundingClientRect();
      var distance = Math.abs((cr.left + cr.width / 2) - center);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = card;
      }
    });

    cards.forEach(function (card) {
      card.classList.toggle('focus', card === best);
    });
  }

  function centerCard(card, behavior) {
    if (!card || !mobile()) return;
    var left = card.offsetLeft - (deck.clientWidth - card.offsetWidth) / 2;
    deck.scrollTo({
      left: Math.max(0, left),
      behavior: behavior || 'auto'
    });
  }

  function scheduleFocus() {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(updateFocus);
  }

  function syncAfterRender(force) {
    var selected = selectedCard();
    var selectedRow = selected && selected.querySelector('.row[data-k]');
    var key = selectedRow ? selectedRow.dataset.k : '';
    var target = selected || deck.querySelector('.hcard');
    var shouldCenter = force || key !== lastSelected ||
      !deck.querySelector('.hcard.focus');

    lastSelected = key;

    requestAnimationFrame(function () {
      if (shouldCenter) centerCard(target, 'auto');
      updateFocus();
    });
  }

  deck.addEventListener('scroll', scheduleFocus, { passive: true });

  deck.addEventListener('click', function (event) {
    if (!mobile()) return;
    var card = event.target.closest('.hcard');
    if (!card || card.classList.contains('focus')) return;

    event.preventDefault();
    event.stopPropagation();
    centerCard(card, 'smooth');
  });

  window.addEventListener('resize', scheduleFocus);

  new MutationObserver(function () {
    syncAfterRender(false);
  }).observe(deck, { childList: true });

  syncAfterRender(true);
})();
