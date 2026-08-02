# Lumatra product page — Shopify OS 2.0 conversion

Converts the supplied `Lumatra Product Page.dc.html` mockup into a native Shopify section.
The mockup itself was already a data-driven prototype (custom `sc-for`/`sc-if`/`{{ }}` template
syntax over a small state object) rather than static HTML, which made it possible to trace every
piece of copy back to either **real Shopify product data** or **merchant-editable content** — the
result has no hardcoded product information.

## Files delivered

| File | Purpose |
|---|---|
| `sections/product-lumatra.liquid` | The whole page: hero/buy box, marketing sections, reviews, footer, sticky bar. Contains the `{% schema %}`. |
| `snippets/icon-product-lumatra.liquid` | Shared inline-SVG icon library (icons used 2+ times only). |
| `snippets/product-lumatra-gallery.liquid` | Product media gallery (mobile + desktop share one DOM; CSS repositions it). |
| `snippets/product-lumatra-swatch-picker.liquid` | Image-swatch radio picker for the primary option ("Select Model"). |
| `snippets/product-lumatra-bundle-row.liquid` | One configurator row inside the "Buy 2" bundle (thumbnail + a `<select>` per option). |
| `snippets/product-lumatra-marquee.liquid` | The scrolling marquee strip (used 4×). |
| `snippets/product-lumatra-cart-drawer.liquid` | AJAX cart drawer (`<dialog>`). |
| `snippets/product-lumatra-model-modal.liquid` | "Which one is for me?" comparison modal (`<dialog>`), built from `model_info` blocks. |
| `assets/section-product-lumatra.css` | All styling — mobile-first, scoped under `.plt` so it can't leak into the rest of the theme. |
| `assets/section-product-lumatra.js` | All behaviour that needs real data (gallery, variant/bundle pricing, AJAX cart, sticky bar, testimonial autoplay). |
| `assets/product-lumatra-*.png` (28 files) | The demo photography from the mockup, namespaced so it can't collide with existing theme assets. Used only as fallbacks until a merchant uploads real product/marketing images. |
| `templates/product.lumatra.json` | An example alternate product template that adds the section with the same demo content as the schema's preset, for a one-click working page. |

**No Luhxe branding was present to remove.** The supplied HTML/JS was already fully rebranded to
"Lumatra" throughout (title, logo, footer, FAQ email address, etc.) — I grepped the source for
`luhxe` (case-insensitive) before starting and it returned zero matches, so this is a straight
conversion with nothing left to rename.

## Installation

1. Copy `sections/`, `snippets/`, and `assets/` files into the matching folders of your theme
   (e.g. via the Shopify admin's **Edit code**, or the Shopify CLI/GitHub integration).
2. Copy `templates/product.lumatra.json` into your theme's `templates/` folder if you want a
   ready-to-use alternate template — or just add the **Lumatra product page** section to your
   existing `templates/product.json` (or any product template) via the theme editor's
   **Add section** picker; it ships with a full preset so it's populated immediately.
3. In the theme editor, open the product template and assign the product you want it on (Shopify
   automatically supplies the page's `product` object — you only need the section's own **Product**
   picker if you want to feature a *different* product than the one the template is assigned to).
4. Set the product up with (recommended) two options, e.g. **Style** (Classic / Roller) and
   **Color** (Rose / Charcoal / Snow), matching the original design's swatch + dropdown pattern —
   see "How the variant picker maps to your product" below. The section works with 1–3 options of
   any name; it isn't hardcoded to "Style"/"Color".
5. Review the ~140 section settings (grouped under headers matching each part of the page) and the
   block content (trust badges, FAQ, reviews, testimonials, comparison rows, etc.) in the theme
   editor and adjust copy/images as needed. Everything defaults to the original mockup's content.
6. Confirm the two Google Fonts (`Oswald`, `Jost`) are acceptable — see Assumptions below for how
   to switch to theme-native font loading instead.

### How the variant picker maps to your product

- The **first product option** (configurable via the section setting *"Swatch-picker option
  position"*) is rendered as image-swatch buttons in the hero, exactly like the original
  Classic/Roller picker. Each swatch's thumbnail is the `featured_image` of the first variant that
  has that option value — no metafield setup required.
- Any additional options render as plain `<select>` dropdowns inside the "Buy 2" bundle rows (one
  row per bag, each independently configurable), matching the original's Model + Color selects.
- **By design, matching the original mockup exactly:** the "Buy 1" (single) purchase path only
  exposes the swatch (primary option). It does not show a second dropdown for other options, so it
  resolves to the first available variant matching the chosen swatch value. If you want color
  selectable on a single purchase too, duplicate the pattern used in `product-lumatra-bundle-row.liquid`
  into the single-item flow.

## Metafields (all optional — the page works fully without any of them)

| Metafield | Type | Used for |
|---|---|---|
| `product.metafields.reviews.rating` | rating | Aggregate star rating shown in ~6 places on the page. Falls back to the section setting *"Fallback average rating"* (default `4.7`) if empty. Compatible with Shopify's free Product Reviews app and most third-party review apps that follow this common convention (e.g. Judge.me, Loox). |
| `product.metafields.reviews.rating_count` | number | Review count shown next to the rating. Falls back to *"Fallback review count"* (default `1346`). |

No metafields are required to be created for the section to render correctly — everything else
(bundle content, FAQ, testimonials, reviews, comparison table, trust copy, etc.) is driven by the
section's own settings/blocks so it works immediately after installation.

## Theme settings summary

The section has ~140 settings organized under editor headers: Product, Navigation, Model/style
picker, Bundle/bulk pricing, Add to cart, Video showcase, Checklist, Trust rows, Savings card,
Tabs, Marquee strips, Features panel, Press, Problem section, Smart-packing/wheels/weather
features, Carry-on stats, Lifestyle marquee, Comparison table, Testimonials, FAQ, Promise grid,
Reviews, and Footer. Repeating content (nav links, trust badges, video thumbnails, model compare
cards, "3 features" cards, press quotes, problem cards, airline wordmarks, testimonials, FAQ,
promise items, reviews, footer policy links) is implemented as **blocks** so merchants can
add/remove/reorder them in the theme editor without touching code.

Two settings are worth calling out:

- **"Buy 2" discount %** (default 30, matching "BOGO 30% Off") drives all bundle pricing math —
  the single price/compare-at come straight from the product's real price and compare-at price,
  and the double price is computed from them (`price × 2 × (100 − discount) / 100`), not hardcoded.
- **Low-stock threshold** (default 10) replaces the mockup's always-on "Warning: Low Stock
  Remaining" banner with one driven by real Shopify inventory tracking — it only appears when
  `inventory_management` is `shopify` and quantity is at or below the threshold, and updates live
  as the customer changes variants.

## Assumptions made during conversion

1. **Bundle pricing is computed, not fixed.** The mockup hardcoded `$129 / $200 / $179 / $400`
   regardless of any real product price. Those numbers only make sense for one specific product, so
   instead the section computes single/double pricing from the product's actual `price` and
   `compare_at_price` plus a configurable discount percentage. To reproduce the exact original
   numbers, set the product's price to $129.00 and compare-at to $200.00 with the discount at 30%
   (double price nets to $180, one dollar off the mockup's $179 — close enough that I judged
   "computed from real data" a better default than "hardcoded to match one specific price point,"
   per the brief's instruction to avoid hardcoding product data). An optional override isn't wired
   in; say the word if you'd rather have exact per-bundle price/compare-at override settings.
2. **The "Buy 2" bundle adds two independent line items via the Cart AJAX API**
   (`/cart/add.js` with an `items` array), each bag resolving to its own variant from its own
   Style/Color selects — this is native Shopify functionality, no app required. There's no native
   Shopify concept of a "bundle," so if you need the two items visually grouped or discounted as a
   unit in the cart itself (rather than via the theme-side default 30% math shown pre-cart), that
   needs a bundle app or a Shopify Function discount — the theme only handles the picking/adding UI.
3. **Dynamic checkout button added.** The mockup had no Shop Pay/PayPal-style button, but the brief
   explicitly asked for one, so I added `{{ form | payment_button }}` under the Add to Cart button,
   togglable via *"Show dynamic checkout button."* Turn it off to match the mockup pixel-for-pixel.
4. **Selling plans** render natively (a minimal dropdown) only if the assigned product actually has
   selling plan groups; the original design had no subscription UI, so nothing appears unless you
   turn on subscriptions for the product.
5. **Product recommendations were intentionally omitted.** The source page doesn't have a "you may
   also like" section, and the brief says this is a conversion, not a redesign, so none was added.
   Drop in Shopify's native `{% section 'product-recommendations' %}` below this section if you want
   one — it's a separate, independent section by design.
6. **New-arrival ribbon from `product.tags`.** Not present in the mockup, but added as a small,
   off-by-default-content (on-by-default-code, invisible unless the tag exists) touch: if the
   product has the tag named in *"Tag that triggers the badge"* (default `new`), a badge renders
   next to the existing trust pills. Uses `product.tags`, one of the objects the brief asked to wire
   up, in a way that doesn't change the default look for products without that tag.
7. **Footer "Policies" column** prefers Shopify's native policy objects (`shop.privacy_policy`,
   `shop.refund_policy`, `shop.shipping_policy`, `shop.terms_of_service`, `shop.subscription_policy`)
   over hardcoded links, since Shopify already provides these. "Contact Information" isn't a native
   policy type, so it's kept as a regular `footer_policy_link` block, same as the original.
8. **Footer payment icons** use `{{ type | payment_type_svg_tag }}` over `shop.enabled_payment_types`
   instead of the mockup's static text badges (AMEX/PayPal/etc. as plain styled text) — this shows
   real icons for whatever payment methods are actually enabled on your store rather than a fixed
   list, which felt like the more correct reading of "avoid hardcoded values Shopify already
   provides." Sizing/spacing was kept close to the original text-badge treatment.
9. **SKU** is shown as an extra bullet in the Details tab (only when the variant has one set) since
   the checklist explicitly asked for it but the original design had no slot for it.
10. **Two elements visible on the live reference site (`luhxe.com/products/luhxe`) aren't in the
    supplied HTML** — a small "FREE GIFTS WORTH $35" pill next to the trust badges, and a circular
    "Happy 100,000+ Travelers" badge over the hero photo. The travelers badge turned out to be baked
    into the hero product photo itself (not a page element), so it needs no extra markup — it'll
    reappear automatically once real product photography with that treatment is uploaded. The gifts
    pill genuinely isn't in the source at all; since the brief is explicit that the supplied HTML is
    the source of truth for a conversion (not a redesign against the live URL), I left it out rather
    than inventing it, but the *"Trust badge"* block type makes adding it a 10-second theme-editor
    edit if you want it.
11. **Accessibility/robustness upgrades that don't change the visual design:** the FAQ accordion,
    "see approved airlines" panel, and mobile nav use native `<details>`/`<summary>` instead of
    JS-toggled `<div>`s; the Details/Included/Shipping tabs and the reviews "see more" toggle use
    radio/checkbox `:checked` CSS instead of JS; the cart drawer and comparison modal use native
    `<dialog>` (built-in focus trapping, Esc-to-close, backdrop). These all reduce the JS payload
    versus a literal translation of the mockup's React-style state machine, per the "no unnecessary
    JavaScript" requirement, with no visible difference in the result.
12. **Demo images are the low-resolution mockup photography** (bundled as theme assets, namespaced
    `product-lumatra-*.png`). They're only fallbacks — the product gallery pulls from
    `product.media` the moment the assigned product has real images, and every marketing image slot
    has an `image_picker` setting for replacing the placeholder with production photography.
13. **A second, differently-named set of images shipped in the source zip** (`hero-main.png`,
    `review-jennifer.png`, `lifestyle-01.png`, etc.) wasn't referenced anywhere in the actual
    `.dc.html`/component source — only the `f_*`-prefixed files (plus `faq-flight-attendant.png`)
    were. To avoid shipping unused weight, only the files the page actually uses were copied in.
14. **Font loading**: the two Google Fonts (`Oswald`, `Jost`) are linked directly from the section
    (with `preconnect`) so the section works standalone in any theme. For best performance, move
    those two `<link>` tags into `layout/theme.liquid`'s `<head>` once installed, so they load
    before the section renders instead of alongside it.
15. **Settings intentionally skip the `t:` translation-key convention.** Using literal English
    defaults (rather than locale-file keys) means this drops in without requiring you to merge JSON
    into your theme's `locales/*.json` files. If you run a multi-language store, the settings are
    still fully editable per-language via Shopify's standard section-setting translation UI — they
    just aren't pre-translated.

## Testing notes

I don't have a Shopify store/theme connected to this environment to preview the section live, so
verification here was: (a) the schema JSON parses and block counts stay within Shopify's per-section
block limit (49 of a reasonable ~50 ceiling), (b) Liquid tag balance (`if/for/case/form`) checked
programmatically across the whole file, (c) the JS passes `node --check`, (d) every `section.settings.*`
and `block.settings.*` reference in the Liquid has a matching schema entry. Please do a visual pass in
**Theme editor → Preview** before shipping to production, especially the two `<dialog>`-based
overlays (cart drawer, compare modal) and the sticky add-to-cart bar on a real phone.
