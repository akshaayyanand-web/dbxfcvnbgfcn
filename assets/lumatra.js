(function () {
  if (window.__lmJsLoaded) return;
  window.__lmJsLoaded = true;

  // Accordion (FAQ + Details/Included/Shipping) — same event-delegation pattern as lux-cove.js.
  document.addEventListener('click', function (e) {
    var toggle = e.target.closest('[data-lm-toggle]');
    if (!toggle) return;
    var body = toggle.parentElement.querySelector('[data-lm-body]');
    var chev = toggle.querySelector('[data-lm-chev]');
    var isOpen = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!isOpen));
    if (body) body.hidden = isOpen;
    if (chev) chev.classList.toggle('lm-open', !isOpen);
  });

  // "Buy 2 & Save" bundle picker — sets Horizon's native quantity input rather than
  // reimplementing cart logic, so the actual Add to Cart button (native buy-buttons
  // block) stays the single source of truth for what gets added to the real cart.
  document.addEventListener('change', function (e) {
    var radio = e.target.closest('[data-lm-bundle-radio]');
    if (!radio) return;
    var qty = radio.value === 'double' ? 2 : 1;
    var form = document.querySelector('product-form-component form[data-type="add-to-cart-form"]') || document.querySelector('form[data-type="add-to-cart-form"]');
    var qtyInput = form ? form.querySelector('input[name="quantity"]') : document.querySelector('input[name="quantity"]');
    if (!qtyInput) return;
    qtyInput.value = String(qty);
    qtyInput.dispatchEvent(new Event('input', { bubbles: true }));
    qtyInput.dispatchEvent(new Event('change', { bubbles: true }));
  });
})();
