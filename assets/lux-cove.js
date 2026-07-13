(function(){
  if (window.__lcJsLoaded) return;
  window.__lcJsLoaded = true;

  document.addEventListener('click', function(e){
    var toggle = e.target.closest('[data-lc-toggle]');
    if (toggle) {
      var body = toggle.parentElement.querySelector('[data-lc-body]');
      var chev = toggle.querySelector('[data-lc-chev]');
      var isOpen = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!isOpen));
      if (body) body.hidden = isOpen;
      if (chev) chev.classList.toggle('lc-open', !isOpen);
      return;
    }

    var thumb = e.target.closest('[data-lc-thumb]');
    if (thumb) {
      var gallery = thumb.closest('[data-lc-gallery]');
      if (!gallery) return;
      var hero = gallery.querySelector('[data-lc-hero-img]');
      if (hero) hero.src = thumb.getAttribute('data-lc-full');
      gallery.querySelectorAll('[data-lc-thumb]').forEach(function(t){ t.classList.remove('lc-on'); });
      thumb.classList.add('lc-on');
      return;
    }
  });

  function addToCart(form){
    var button = form.querySelector('[type="submit"]');
    var idInput = form.querySelector('[name="id"]');
    if (!idInput || !idInput.value) return;
    if (button) { button.disabled = true; button.dataset.lcLabel = button.textContent; button.textContent = 'Adding...'; }
    fetch('/cart/add.js', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ id: idInput.value, quantity: 1 })
    })
    .then(function(res){ return res.json(); })
    .then(function(){
      document.dispatchEvent(new CustomEvent('cart:refresh'));
      window.location.href = '/cart';
    })
    .catch(function(){
      if (button) { button.textContent = 'Something went wrong'; }
    })
    .finally(function(){
      if (button) { setTimeout(function(){ button.disabled = false; button.textContent = button.dataset.lcLabel; }, 1200); }
    });
  }

  document.addEventListener('submit', function(e){
    var form = e.target.closest('[data-lc-add-to-cart]');
    if (!form) return;
    e.preventDefault();
    addToCart(form);
  });

  function syncVariant(form){
    var script = form.querySelector('[data-lc-variants]');
    var selects = Array.prototype.slice.call(form.querySelectorAll('[data-lc-option-selector]'));
    if (!script || !selects.length) return;
    var variants;
    try { variants = JSON.parse(script.textContent); } catch (err) { return; }
    var values = selects
      .sort(function(a, b){ return a.getAttribute('data-lc-option-position') - b.getAttribute('data-lc-option-position'); })
      .map(function(s){ return s.value; });
    var match = variants.filter(function(v){
      return v.options.length === values.length && v.options.every(function(o, i){ return o === values[i]; });
    })[0];
    if (!match) return;

    var idInput = form.querySelector('[data-lc-variant-id]');
    if (idInput) idInput.value = match.id;

    var ctaButton = form.querySelector('[data-lc-cta-button]');
    if (ctaButton) {
      ctaButton.disabled = !match.available;
      ctaButton.textContent = match.available ? (ctaButton.getAttribute('data-lc-add-label') + match.price) : 'Sold Out';
    }

    var buybarButton = document.querySelector('[data-lc-buybar-button][form="' + form.id + '"]');
    if (buybarButton) {
      buybarButton.disabled = !match.available;
      buybarButton.textContent = match.available ? 'Add to Cart' : 'Sold Out';
    }
    var buybarPrice = document.querySelector('[data-lc-buybar-price]');
    if (buybarPrice) buybarPrice.textContent = match.price;
    var buybarCompare = document.querySelector('[data-lc-buybar-compare]');
    if (buybarCompare) {
      if (match.comparePrice) { buybarCompare.textContent = match.comparePrice; buybarCompare.hidden = false; }
      else { buybarCompare.hidden = true; }
    }
  }

  document.addEventListener('change', function(e){
    var selector = e.target.closest('[data-lc-option-selector]');
    if (!selector) return;
    var form = selector.closest('form');
    if (form) syncVariant(form);
  });
})();
