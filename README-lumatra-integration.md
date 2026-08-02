# Lumatra product page — integrated into the Horizon theme

Your theme export (`wwwlumatraplmaintheme`, Shopify Horizon 4.1.1) already had a working pattern
for exactly this kind of page: the `lux-cove-*` section family, wired into `product.lux-cove.json`
and `product.lux-cove-facial-sculptor.json`. Rather than dropping in a self-contained page (which
would have meant a second header, a second cart drawer, and a second add-to-cart flow fighting your
real one), this follows that same pattern — a `lumatrastyle` token override plus a family of
`lumatra-*` sections layered under Horizon's own **Product information** section.

The earlier standalone build from this session (a fully self-contained `sections/product-lumatra.liquid`
with its own header/cart-drawer/gallery) has been removed — it doesn't apply here, and keeping it
alongside a real theme would just be confusing dead code.

## What's new

| File | Purpose |
|---|---|
| `sections/lumatrastyle.liquid` | Loads Oswald/Jost and remaps Horizon's `--color-*`/`--font-*` tokens to Lumatra's cream/ink/maroon palette, scoped to this template only (same mechanism as your existing `luxcovestyle.liquid`). |
| `sections/lumatra-buybox-extras.liquid` | Everything under the native buy box that Horizon doesn't provide: trust pills, the Buy 1 / Buy 2 & Save pricing picker, the "why women love it" checklist, trust rows + airline list, video showcase, the savings calculator, and a Details/Included/Shipping/Which-one-is-for-me accordion. |
| `sections/lumatra-feature.liquid` | One image+text feature card. Used 3× for the "3 Features" row. |
| `sections/lumatra-press.liquid` | "As seen in" press quotes. |
| `sections/lumatra-problem.liquid` | The 4 problem cards + the "smart packing" video/copy feature. |
| `sections/lumatra-split.liquid` | Reusable image/copy split — reused for wheels & handle, weather/durability, and the carry-on savings stats, via optional blocks (`mini_feature`, `airline_logo`, `stat_card`). |
| `sections/lumatra-marquee-text.liquid` | The scrolling promo/sale/new-customer text banners (used 5×). |
| `sections/lumatra-lifestyle-marquee.liquid` | The scrolling lifestyle-photo loop. |
| `sections/lumatra-comparison.liquid` | The "US vs Them" table. |
| `sections/lumatra-testimonial.liquid` | Scrolling testimonial pill marquee. |
| `sections/lumatra-faq.liquid` | FAQ accordion. |
| `sections/lumatra-reviews.liquid` | Rating histogram + review masonry grid with a "see more" toggle. |
| `sections/lumatra-promise.liquid` | The 4-icon trust/promise grid. |
| `assets/lumatra.css` / `assets/lumatra.js` | Shared styles (namespaced `lm-*`, mirrors `lux-cove.css`'s structure) and the one shared behavior: an accordion click-delegate (same pattern as `lux-cove.js`) plus the bundle-picker's quantity nudge. |
| `assets/lumatra-*.png` (15 files) | Demo photography, used as fallback images until you pick real ones — same `image_picker → fallback select → bundled asset` pattern your `lux-cove-*` sections already use. |
| `templates/product.lumatra-travel-bag.json` | Composes all of the above in the same order as the original page, with Horizon's native **Product information** section as `main`. |

## Installation

1. The files are already in the right folders (`sections/`, `assets/`, `templates/`) — push/deploy
   this theme as usual, or copy these specific files into your live theme via **Edit code**.
2. In Shopify admin, open the **Lumatra Travel Bag 2.0** product → **Theme templates** → select
   **lumatra-travel-bag** (or whichever product you want this page on — the template isn't
   pre-assigned to any product, since I don't have access to your product catalog from here).
3. Set the product up with two options — e.g. **Style** (Classic / Roller) and **Color** (Rose /
   Charcoal / Snow) — so Horizon's native variant picker in the buy box shows the same swatch +
   dropdown pattern as the original design. Variant images become the swatch thumbnails
   automatically; no metafields needed.
4. Open the theme editor on that product page and check each `lumatra-*` section's settings —
   everything defaults to the original copy, but block content (FAQ, reviews, testimonials, press
   quotes, comparison rows, etc.) is fully editable there.

## How the buy box actually works now

The gallery, variant picker, price, quantity, Add to Cart button, dynamic checkout button, and
sticky add-to-cart bar are all Horizon's **native** `product-information` section — not rebuilt.
That's a deliberate change from a generic drop-in build: Horizon's cart is a real component system
(`cart-icon`, `cart-drawer`, `fly-to-cart`, quantity rules, etc.), and reimplementing an independent
AJAX cart next to it risks a header cart icon that doesn't update, or an animation that doesn't fire,
things I can't fully verify without a live preview of your store. Using the real one guarantees it's
correct.

One consequence: the **"Buy 2 & Save 30%"** picker in `lumatra-buybox-extras` no longer adds two
independently-configured bags (Bag 1: Classic/Rose, Bag 2: Roller/Charcoal) as two separate cart
lines the way the original mockup implied. Instead, picking "Buy 2" sets Horizon's native quantity
input to 2 for whatever variant is currently selected in the buy box above, and the real Add to Cart
button (native, right above this section) does the actual adding. You keep the bulk-pricing message
and the conversion mechanic; you lose the "two different colors in one bundle" nuance. If you want
that back, it needs either a bundle app (so the two-line-item cart behavior is handled by tested,
supported code) or a Shopify Function discount pattern — happy to wire either up if you tell me
which you'd rather use.

Bundle pricing itself is still fully computed, not hardcoded: single price/compare-at come from the
product's real price, and the double price is `price × 2 × (100 − discount%) / 100` (discount % is
a section setting, defaulting to 30 to match "BOGO 30% Off").

## Metafield (optional)

`product.metafields.reviews.rating` / `reviews.rating_count` — used for the aggregate rating shown
in the buy box and reviews section, with a text-setting fallback (4.7 / 1346) if you haven't set it
up. Compatible with Shopify's Product Reviews app or similar apps that follow this convention.

## Things worth checking in the theme editor before this goes live

- I don't have a live preview of your store, so I've verified this the only ways I can from here:
  every section's schema JSON parses, every setting/block reference in the template matches its
  section's schema, Liquid tag balance, CSS brace balance, JS syntax, and every bundled fallback
  image resolves to a real file. A visual pass in **Theme editor → Preview**, especially on mobile
  and with the sticky add-to-cart bar, is still worth doing.
- `lumatrastyle`'s `template_suffix` setting must keep matching the template filename
  (`lumatra-travel-bag`) if you ever rename `templates/product.lumatra-travel-bag.json`.
- The "Configure Your Bag" CTA buttons in `lumatra-problem` and `lumatra-comparison` currently link
  to `#` — point them at your buy box (or leave them as scroll-to-top style anchors) once you know
  where you want them to land.
