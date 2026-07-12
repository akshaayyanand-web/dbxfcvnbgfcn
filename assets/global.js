(function () {
  'use strict';

  function openDrawer(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.add('is-open');
    el.setAttribute('open', '');
    var panel = el.querySelector('.drawer__panel');
    if (panel) panel.focus();
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer(el) {
    el.classList.remove('is-open');
    el.removeAttribute('open');
    document.body.style.overflow = '';
  }

  document.addEventListener('click', function (event) {
    var opener = event.target.closest('[data-drawer-open]');
    if (opener) {
      openDrawer(opener.getAttribute('data-drawer-open'));
      return;
    }

    var closer = event.target.closest('[data-drawer-close]');
    if (closer) {
      var drawer = closer.closest('.drawer');
      if (drawer) closeDrawer(drawer);
      return;
    }

    var menuToggle = event.target.closest('[data-menu-toggle]');
    if (menuToggle) {
      var expanded = menuToggle.getAttribute('aria-expanded') === 'true';
      menuToggle.setAttribute('aria-expanded', String(!expanded));
      var nav = document.getElementById(menuToggle.getAttribute('aria-controls'));
      if (nav) nav.classList.toggle('is-open', !expanded);
      return;
    }

    var chatToggle = event.target.closest('[data-chat-toggle]');
    if (chatToggle) {
      document.body.classList.toggle('chat-widget-open');
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape') return;
    document.querySelectorAll('.drawer.is-open').forEach(closeDrawer);
  });

  document.addEventListener('change', function (event) {
    var qtyInput = event.target.closest('[data-cart-line]');
    if (!qtyInput) return;

    var line = qtyInput.getAttribute('data-cart-line');
    var quantity = parseInt(qtyInput.value, 10) || 0;

    fetch('/cart/change.js', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ line: line, quantity: quantity }),
    })
      .then(function (response) { return response.json(); })
      .then(function (cart) {
        var countEl = document.querySelector('[data-cart-count]');
        if (countEl) countEl.textContent = cart.item_count;
      });
  });

  var header = document.querySelector('header-bar[data-sticky="true"]');
  if (header) {
    var lastScroll = window.scrollY;
    window.addEventListener(
      'scroll',
      function () {
        var current = window.scrollY;
        header.classList.toggle('is-scrolled', current > 10);
        lastScroll = current;
      },
      { passive: true }
    );
  }
})();
