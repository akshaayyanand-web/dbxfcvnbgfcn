/**
 * Lumatra product page — behaviour for sections/product-lumatra.liquid.
 * Mobile nav, tabs, FAQ, "see more reviews" and the airline list are handled with
 * native <details>/radio/checkbox CSS and need no JS. This file owns everything
 * that needs real data: the media gallery, variant/bundle resolution + pricing,
 * the AJAX cart, the sticky add-to-cart bar, and the testimonial carousel.
 */
(function () {
  'use strict';

  function formatMoney(cents, format) {
    if (typeof cents !== 'number' || isNaN(cents)) cents = 0;
    format = format || '${{amount}}';
    var value = cents / 100;

    function withDecimals(n, sep) {
      var parts = n.toFixed(2).split('.');
      return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, sep || ',') + '.' + parts[1];
    }
    function noDecimals(n, sep) {
      return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, sep || ',');
    }

    var token = /\{\{\s*(\w+)\s*\}\}/.exec(format);
    var body;
    switch (token && token[1]) {
      case 'amount_no_decimals':
        body = noDecimals(value, ',');
        break;
      case 'amount_with_comma_separator':
        body = withDecimals(value, ',').replace(',', 'X').replace('.', ',').replace('X', '.');
        break;
      case 'amount_no_decimals_with_comma_separator':
        body = noDecimals(value, '.');
        break;
      case 'amount_with_space_separator':
        body = withDecimals(value, ' ').replace('.', ',');
        break;
      case 'amount_no_decimals_with_space_separator':
        body = noDecimals(value, ' ');
        break;
      default:
        body = withDecimals(value, ',');
    }
    return token ? format.replace(token[0], body) : format.replace('{{amount}}', body);
  }

  function safeJsonParse(text, fallback) {
    try { return JSON.parse(text); } catch (e) { return fallback; }
  }

  function initSection(root) {
    var configEl = root.querySelector('script[data-plt-config]');
    var config = configEl ? safeJsonParse(configEl.textContent, {}) : {};
    var variants = Array.isArray(config.variants) ? config.variants : [];
    var moneyFormat = config.moneyFormat || '${{amount}}';
    var discountPercent = typeof config.bundleDiscountPercent === 'number' ? config.bundleDiscountPercent : 30;
    var lowStockThreshold = typeof config.lowStockThreshold === 'number' ? config.lowStockThreshold : 10;
    var labels = config.labels || {};

    var form = root.querySelector('.plt-product-form');
    var variantIdInput = root.querySelector('[data-plt-form-variant-id]');
    var quantityInput = root.querySelector('[data-plt-form-quantity]');
    var atcButton = root.querySelector('[data-plt-atc]');

    /* ---------------------------------------------------------------------
     * Variant resolution
     * ------------------------------------------------------------------- */
    function variantById(id) {
      id = String(id);
      for (var i = 0; i < variants.length; i++) {
        if (String(variants[i].id) === id) return variants[i];
      }
      return null;
    }

    function variantByOptions(selections) {
      // selections: { "1": "Classic", "2": "Rose" } keyed by 1-based option position
      var positions = Object.keys(selections);
      var exact = variants.filter(function (v) {
        return positions.every(function (pos) {
          return v.options && v.options[Number(pos) - 1] === selections[pos];
        });
      });
      return exact.find(function (v) { return v.available; }) || exact[0] || null;
    }

    function firstVariantForPrimaryValue(position, value) {
      var matches = variants.filter(function (v) { return v.options && v.options[Number(position) - 1] === value; });
      return matches.find(function (v) { return v.available; }) || matches[0] || variants[0] || null;
    }

    /* ---------------------------------------------------------------------
     * Pricing
     * ------------------------------------------------------------------- */
    function computePricing(variant) {
      var price = variant ? variant.price : 0;
      var rawCompare = variant ? variant.compare_at_price : null;
      var compare = rawCompare && rawCompare > price ? rawCompare : null;
      var doublePrice = Math.floor((price * 2 * (100 - discountPercent)) / 100);
      var doubleEach = Math.floor(doublePrice / 2);
      var doubleCompare = (compare || price) * 2;
      return { price: price, compare: compare, doublePrice: doublePrice, doubleEach: doubleEach, doubleCompare: doubleCompare };
    }

    function currentBundleMode() {
      var checked = root.querySelector('[data-plt-bundle-radio]:checked');
      return checked ? checked.value : 'double';
    }

    function setText(selector, text) {
      var el = root.querySelector(selector);
      if (el) el.textContent = text;
    }

    function renderPricing(variant) {
      var p = computePricing(variant);

      setText('[data-plt-bundle-single-price]', formatMoney(p.price, moneyFormat));
      var singleCompareEl = root.querySelector('[data-plt-bundle-single-compare]');
      if (singleCompareEl) {
        singleCompareEl.hidden = !p.compare;
        singleCompareEl.textContent = p.compare ? formatMoney(p.compare, moneyFormat) : '';
      }

      setText('[data-plt-bundle-double-price]', formatMoney(p.doublePrice, moneyFormat));
      setText('[data-plt-bundle-double-compare]', formatMoney(p.doubleCompare, moneyFormat));
      setText('[data-plt-bundle-each]', formatMoney(p.doubleEach, moneyFormat));

      var mode = currentBundleMode();
      var atcPrice = mode === 'double' ? p.doublePrice : p.price;
      var atcCompare = mode === 'double' ? p.doubleCompare : p.compare;
      setText('[data-plt-atc-price]', formatMoney(atcPrice, moneyFormat));
      setText('[data-plt-atc-compare]', atcCompare ? formatMoney(atcCompare, moneyFormat) : '');
      setText('[data-plt-sticky-price]', formatMoney(atcPrice, moneyFormat));
      setText('[data-plt-sticky-compare]', atcCompare ? formatMoney(atcCompare, moneyFormat) : '');

      if (quantityInput) quantityInput.value = mode === 'double' ? '2' : '1';
    }

    function renderAvailability(variant) {
      var available = !variant || variant.available;
      if (atcButton) {
        atcButton.disabled = !available;
        var availableLine = atcButton.querySelector('[data-plt-atc-available-line]');
        var soldOutLine = atcButton.querySelector('[data-plt-atc-soldout-line]');
        var sub = atcButton.querySelector('[data-plt-atc-sub]');
        if (availableLine) availableLine.hidden = !available;
        if (sub) sub.hidden = !available;
        if (soldOutLine) soldOutLine.hidden = available;
      }

      var warning = root.querySelector('[data-plt-stock-warning]');
      if (warning) {
        var tracked = variant && variant.inventory_management === 'shopify';
        var qty = variant ? variant.inventory_quantity : null;
        var show = !!(tracked && typeof qty === 'number' && qty > 0 && qty <= lowStockThreshold);
        warning.hidden = !show;
      }
    }

    /* ---------------------------------------------------------------------
     * Media gallery
     * ------------------------------------------------------------------- */
    var gallery = root.querySelector('[data-plt-gallery]');
    var variantMediaMap = {};
    if (gallery) {
      var mapEl = gallery.querySelector('script[data-plt-variant-media-map]');
      if (mapEl) variantMediaMap = safeJsonParse(mapEl.textContent, {});

      gallery.addEventListener('click', function (event) {
        var thumb = event.target.closest('[data-plt-gallery-thumb]');
        var demoThumb = event.target.closest('[data-plt-gallery-thumb-demo]');
        if (thumb) {
          selectMedia(thumb.dataset.mediaId);
        } else if (demoThumb) {
          selectDemoThumb(demoThumb);
        }
      });
    }

    function selectMedia(mediaId) {
      if (!gallery || !mediaId) return;
      var template = gallery.querySelector('template[data-plt-media-template][data-media-id="' + mediaId + '"]');
      var mainViewer = gallery.querySelector('[data-plt-gallery-main]');
      if (!template || !mainViewer) return;
      mainViewer.innerHTML = '';
      mainViewer.appendChild(template.content.cloneNode(true));

      gallery.querySelectorAll('[data-plt-gallery-thumb]').forEach(function (btn) {
        var isSelected = btn.dataset.mediaId === mediaId;
        btn.classList.toggle('is-selected', isSelected);
        btn.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      });
    }

    function selectDemoThumb(demoThumb) {
      if (!gallery) return;
      var img = demoThumb.querySelector('img');
      var mainImage = gallery.querySelector('[data-plt-gallery-main-image]');
      if (img && mainImage) mainImage.src = img.src;
      gallery.querySelectorAll('[data-plt-gallery-thumb-demo]').forEach(function (btn) {
        btn.classList.toggle('is-selected', btn === demoThumb);
      });
    }

    function syncGalleryToVariant(variant) {
      if (!variant) return;
      var mediaId = variantMediaMap[String(variant.id)];
      if (mediaId) selectMedia(String(mediaId));
    }

    /* ---------------------------------------------------------------------
     * Hero swatch (primary option) — drives the "Buy 1" resolved variant
     * ------------------------------------------------------------------- */
    var heroVariant = variantById((variantIdInput && variantIdInput.value) || (variants[0] && variants[0].id));

    function handleHeroOptionChange(input) {
      var position = input.dataset.pltOptionPosition;
      var variant = firstVariantForPrimaryValue(position, input.value);
      if (!variant) return;
      heroVariant = variant;

      setText('[data-plt-model-current-value]', input.value);
      if (variantIdInput) variantIdInput.value = variant.id;

      syncGalleryToVariant(variant);
      renderPricing(currentBundleMode() === 'single' ? variant : heroVariant);
      renderAvailability(currentBundleMode() === 'single' ? variant : heroVariant);
      updateStickyThumb(variant);
    }

    root.querySelectorAll('[data-plt-style-swatches] .plt-swatch__input').forEach(function (input) {
      input.addEventListener('change', function () { handleHeroOptionChange(input); });
    });

    function updateStickyThumb(variant) {
      var img = root.querySelector('[data-plt-sticky-thumb]');
      if (!img) return;
      if (variant && variant.featured_image && variant.featured_image.src) {
        img.src = variant.featured_image.src;
      } else if (config.productFeaturedImage) {
        img.src = config.productFeaturedImage;
      }
    }

    /* ---------------------------------------------------------------------
     * Bundle radios (single / double)
     * ------------------------------------------------------------------- */
    root.querySelectorAll('[data-plt-bundle-radio]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        renderPricing(heroVariant);
        renderAvailability(heroVariant);
      });
    });

    /* ---------------------------------------------------------------------
     * Bundle rows (Buy 2 configurator) — each row resolves its own variant
     * ------------------------------------------------------------------- */
    function rowSelections(bag) {
      var selections = {};
      root.querySelectorAll('[data-plt-bundle-row-select="' + bag + '"]').forEach(function (select) {
        selections[select.dataset.pltOptionPosition] = select.value;
      });
      return selections;
    }

    function resolveRowVariant(bag) {
      return variantByOptions(rowSelections(bag));
    }

    function updateRowThumb(bag, variant) {
      var row = root.querySelector('[data-plt-bundle-row="' + bag + '"]');
      if (!row) return;
      var img = row.querySelector('[data-plt-bundle-row-thumb] img');
      if (!img) return;
      if (variant && variant.featured_image && variant.featured_image.src) {
        img.src = variant.featured_image.src;
      } else if (config.productFeaturedImage) {
        img.src = config.productFeaturedImage;
      }
    }

    [1, 2].forEach(function (bag) {
      root.querySelectorAll('[data-plt-bundle-row-select="' + bag + '"]').forEach(function (select) {
        select.addEventListener('change', function () {
          updateRowThumb(bag, resolveRowVariant(bag));
        });
      });
    });

    /* ---------------------------------------------------------------------
     * Sticky add-to-cart bar
     * ------------------------------------------------------------------- */
    var stickyBar = root.querySelector('[data-plt-sticky-atc]');
    var sentinel = root.querySelector('[data-plt-sentinel]');
    if (stickyBar && sentinel && 'IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function (entries) {
        stickyBar.classList.toggle('is-visible', !entries[0].isIntersecting);
      }, { threshold: 0 });
      observer.observe(sentinel);
    }

    /* ---------------------------------------------------------------------
     * Model comparison dialog
     * ------------------------------------------------------------------- */
    var modelModal = root.querySelector('dialog[data-plt-model-modal]');
    root.querySelectorAll('[data-plt-model-modal-open]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (modelModal && typeof modelModal.showModal === 'function') modelModal.showModal();
      });
    });
    if (modelModal) {
      modelModal.querySelectorAll('[data-plt-model-modal-close]').forEach(function (btn) {
        btn.addEventListener('click', function () { modelModal.close(); });
      });
      modelModal.addEventListener('click', function (event) {
        if (event.target === modelModal) modelModal.close();
      });
    }

    /* ---------------------------------------------------------------------
     * Testimonial carousel
     * ------------------------------------------------------------------- */
    var testimonialWrap = root.querySelector('[data-plt-testimonial]');
    if (testimonialWrap) {
      var slides = Array.prototype.slice.call(testimonialWrap.querySelectorAll('[data-plt-testimonial-slide]'));
      var dots = Array.prototype.slice.call(testimonialWrap.querySelectorAll('[data-plt-testimonial-dot]'));
      var activeIndex = 0;
      var timer = null;

      function showTestimonial(index) {
        activeIndex = ((index % slides.length) + slides.length) % slides.length;
        slides.forEach(function (slide, i) { slide.classList.toggle('is-active', i === activeIndex); });
        dots.forEach(function (dot, i) { dot.classList.toggle('is-active', i === activeIndex); });
      }

      function restartAutoplay() {
        if (timer) clearInterval(timer);
        if (slides.length > 1) {
          timer = setInterval(function () { showTestimonial(activeIndex + 1); }, 7000);
        }
      }

      dots.forEach(function (dot, i) {
        dot.addEventListener('click', function () {
          showTestimonial(i);
          restartAutoplay();
        });
      });

      if (slides.length > 1) restartAutoplay();
    }

    /* ---------------------------------------------------------------------
     * AJAX cart
     * ------------------------------------------------------------------- */
    var cartDialog = root.querySelector('dialog[data-plt-cart]');
    var cartLineTemplate = root.querySelector('template[data-plt-cart-line-template]');
    var cartLinesEl = root.querySelector('[data-plt-cart-lines]');
    var cartEmptyEl = root.querySelector('[data-plt-cart-empty]');
    var cartFooterEl = root.querySelector('[data-plt-cart-footer]');
    var cartCountEls = root.querySelectorAll('[data-plt-cart-count], [data-plt-header-cart-count]');
    var cartSubtotalEl = root.querySelector('[data-plt-cart-subtotal]');

    function openCart() {
      if (cartDialog && typeof cartDialog.showModal === 'function') cartDialog.showModal();
    }
    function closeCart() {
      if (cartDialog) cartDialog.close();
    }
    root.querySelectorAll('[data-plt-cart-open]').forEach(function (btn) { btn.addEventListener('click', openCart); });
    if (cartDialog) {
      cartDialog.querySelectorAll('[data-plt-cart-close]').forEach(function (btn) { btn.addEventListener('click', closeCart); });
      cartDialog.addEventListener('click', function (event) {
        if (event.target === cartDialog) closeCart();
      });
      cartDialog.addEventListener('cancel', function () {
        /* native ESC handling already closes the dialog; nothing extra to do */
      });
    }

    function renderCart(cart) {
      var count = cart.item_count || 0;
      cartCountEls.forEach(function (el) {
        el.textContent = count;
        el.dataset.count = count;
      });

      if (!cartLinesEl) return;
      cartLinesEl.innerHTML = '';

      var hasLines = cart.items && cart.items.length > 0;
      if (cartEmptyEl) cartEmptyEl.hidden = hasLines;
      if (cartFooterEl) cartFooterEl.hidden = !hasLines;

      if (hasLines && cartLineTemplate) {
        cart.items.forEach(function (item) {
          var node = cartLineTemplate.content.cloneNode(true);
          var img = node.querySelector('img');
          var label = node.querySelector('.plt-cart__line-label');
          var price = node.querySelector('.plt-cart__line-price');
          var removeBtn = node.querySelector('.plt-cart__line-remove');
          if (img) {
            img.src = item.image ? item.image.replace(/(\.[a-zA-Z0-9]+)(\?|$)/, '_100x100$1$2') : '';
            img.alt = item.product_title || '';
          }
          if (label) label.textContent = item.product_title + (item.variant_title ? ' — ' + item.variant_title : '');
          if (price) price.textContent = formatMoney(item.final_line_price, moneyFormat);
          if (removeBtn) removeBtn.dataset.lineKey = item.key;
          cartLinesEl.appendChild(node);
        });
      }

      if (cartSubtotalEl) cartSubtotalEl.textContent = formatMoney(cart.total_price, moneyFormat);
    }

    function fetchCart() {
      return fetch('/cart.js', { headers: { Accept: 'application/json' } })
        .then(function (res) { return res.json(); })
        .then(function (cart) { renderCart(cart); return cart; });
    }

    if (cartLinesEl) {
      cartLinesEl.addEventListener('click', function (event) {
        var btn = event.target.closest('.plt-cart__line-remove');
        if (!btn) return;
        fetch(config.cartChangeUrl || '/cart/change.js', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ id: btn.dataset.lineKey, quantity: 0 }),
        })
          .then(function (res) { return res.json(); })
          .then(renderCart)
          .catch(function (err) { console.error('[product-lumatra] cart remove failed', err); });
      });
    }

    // Reflect the real cart on load, in case items already exist from elsewhere on the site.
    fetchCart().catch(function (err) { console.error('[product-lumatra] cart fetch failed', err); });

    function addToCart(items) {
      return fetch(config.cartAddUrl || '/cart/add.js', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ items: items }),
      }).then(function (res) {
        if (!res.ok) return res.json().then(function (err) { throw err; });
        return res.json();
      });
    }

    function flashButtonError(button, message) {
      if (!button) return;
      var line = button.querySelector('[data-plt-atc-available-line]') || button.querySelector('.plt-atc__line') || button;
      var original = line.textContent;
      line.textContent = message;
      setTimeout(function () {
        if (button === atcButton) {
          // Rebuild from source state rather than restoring flattened text, so the
          // price/compare <span>s inside the button aren't left destroyed.
          renderPricing(heroVariant);
          renderAvailability(heroVariant);
        } else {
          line.textContent = original;
        }
      }, 2500);
    }

    function currentSellingPlanId() {
      var select = form ? form.querySelector('[data-plt-selling-plan-select]') : null;
      return select && select.value ? select.value : null;
    }

    function buildCartItems() {
      var mode = currentBundleMode();
      var sellingPlan = currentSellingPlanId();
      if (mode === 'single') {
        var singleVariant = heroVariant || variantById(variantIdInput && variantIdInput.value);
        if (!singleVariant) return null;
        var singleItem = { id: singleVariant.id, quantity: 1 };
        if (sellingPlan) singleItem.selling_plan = sellingPlan;
        return [singleItem];
      }
      var bag1 = resolveRowVariant(1);
      var bag2 = resolveRowVariant(2);
      if (!bag1 || !bag2) return null;
      var items = [{ id: bag1.id, quantity: 1 }, { id: bag2.id, quantity: 1 }];
      if (sellingPlan) items.forEach(function (item) { item.selling_plan = sellingPlan; });
      return items;
    }

    function handleAddToCart(triggerButton) {
      var items = buildCartItems();
      if (!items) {
        flashButtonError(triggerButton, labels.unavailable || 'Unavailable');
        return;
      }
      var originalDisabled = triggerButton ? triggerButton.disabled : false;
      if (triggerButton) triggerButton.disabled = true;

      addToCart(items)
        .then(function () { return fetchCart(); })
        .then(function () { openCart(); })
        .catch(function (err) {
          console.error('[product-lumatra] add to cart failed', err);
          flashButtonError(triggerButton, (err && err.description) || labels.unavailable || 'Something went wrong');
        })
        .finally(function () {
          if (triggerButton) triggerButton.disabled = originalDisabled;
        });
    }

    if (form) {
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        handleAddToCart(atcButton);
      });
    }

    root.querySelectorAll('[data-plt-quick-add]').forEach(function (btn) {
      btn.addEventListener('click', function () { handleAddToCart(btn); });
    });

    /* ---------------------------------------------------------------------
     * Initial paint
     * ------------------------------------------------------------------- */
    renderPricing(heroVariant);
    renderAvailability(heroVariant);
  }

  function init() {
    document.querySelectorAll('.plt').forEach(initSection);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  document.addEventListener('shopify:section:load', function (event) {
    var root = event.target.querySelector ? event.target.querySelector('.plt') : null;
    if (root) initSection(root);
  });
})();
