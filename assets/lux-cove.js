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
})();
