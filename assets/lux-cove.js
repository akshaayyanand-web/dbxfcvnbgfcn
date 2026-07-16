(function(){
  if (window.__lcJsLoaded) return;
  window.__lcJsLoaded = true;

  document.addEventListener('click', function(e){
    var toggle = e.target.closest('[data-lc-toggle]');
    if (!toggle) return;
    var body = toggle.parentElement.querySelector('[data-lc-body]');
    var chev = toggle.querySelector('[data-lc-chev]');
    var isOpen = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!isOpen));
    if (body) body.hidden = isOpen;
    if (chev) chev.classList.toggle('lc-open', !isOpen);
  });

  // Minimal add-to-cart for the home-page product cards. Uses Shopify's
  // standard /cart/add.js endpoint, then sends the shopper to the cart.
  document.addEventListener('submit', function(e){
    var form = e.target.closest('[data-lc-quick-add]');
    if (!form) return;
    e.preventDefault();
    var button = form.querySelector('[type="submit"]');
    var idInput = form.querySelector('[name="id"]');
    if (!idInput || !idInput.value) return;
    if (button) { button.dataset.lcLabel = button.textContent; button.textContent = 'Adding...'; button.disabled = true; }
    fetch('/cart/add.js', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ id: idInput.value, quantity: 1 })
    })
    .then(function(res){ return res.json(); })
    .then(function(){ window.location.href = '/cart'; })
    .catch(function(){ if (button) { button.textContent = 'Try again'; button.disabled = false; } });
  });
})();
