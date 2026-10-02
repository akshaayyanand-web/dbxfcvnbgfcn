/* Sanctions+ landing page interactivity — the two illustrative demos
   (ownership explorer, adverse-media classification). Vanilla JS port of
   the same demo data used in the design mockup. No network calls: this is
   a static marketing page, not the live app. */
(function () {
  var esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));

  /* ---------------- Ownership explorer ---------------- */
  var NODES = {
    elena: { chain: true, dark: false, title: 'Elena Kovacs', sub: 'Person · CY', badge: 'PEP', badgeClass: 'badge-review', owns: 'owns 55%',
      kind: 'Person · candidate UBO', name: 'Elena Kovacs',
      note: 'Owns 55% of Azure Holdings Cyprus. Recorded as politically exposed (former deputy minister). PEP status is not an allegation; it raises the standard of source-of-funds enquiry.' },
    azure: { chain: true, dark: false, title: 'Azure Holdings Cyprus Ltd', sub: 'HE-402117 · CY', owns: 'owns 60%',
      kind: 'Company · Cyprus', name: 'Azure Holdings Cyprus Ltd',
      note: 'Tier 3. Owns 60% of Marina Bay Investments. Cyprus is on the limited-disclosure jurisdiction list.' },
    marina: { chain: true, dark: false, title: 'Marina Bay Investments (Cayman) Ltd', sub: 'KY-556104 · KY', owns: 'owns 100%',
      kind: 'Company · Cayman Islands', name: 'Marina Bay Investments (Cayman) Ltd',
      note: 'Tier 2. Owns 100% of Falcon Nominees. Director: Marcus Webb, who sits on 9 boards in this network.' },
    nominees: { chain: true, dark: false, title: 'Falcon Nominees Ltd', sub: 'BVI-1902334 · VG', owns: 'owns 76%',
      kind: 'Company · British Virgin Islands', name: 'Falcon Nominees Ltd',
      note: 'Tier 1. Holds 76% of the searched company. Same director as Marina Bay.' },
    falcon: { chain: true, dark: true, title: 'Falcon Capital Holdings FZE', sub: 'DMCC-114872 · Searched entity',
      kind: 'Company · searched entity', name: 'Falcon Capital Holdings FZE',
      note: 'DMCC-114872. Part of a circular ownership loop and one of 5 entities at a shared registered address.' },
    rashid: { chain: false, title: 'Rashid Al Mansoori', tag: '24% of Falcon', sub: 'Person · AE · possible twin record',
      kind: 'Person · shareholder', name: 'Rashid Al Mansoori',
      note: 'Holds 24%. A second record, "Rashid Almansoori", is linked as a possible same person. It has not been merged: verify before treating them as one.' },
    orient: { chain: false, title: 'Orient Star Trading Ltd', tag: '15% of Falcon', sub: 'SC-203991 · SC · in a loop',
      kind: 'Company · Seychelles', name: 'Orient Star Trading Ltd',
      note: 'Owns 15% of Falcon Capital, closing the loop Falcon → Crescent Trade → Orient Star → Falcon.' },
    viktor: { chain: false, title: 'Viktor Branko', badge: 'Sanctioned', badgeClass: 'badge-high', sub: 'Person · 40% of Orient Star',
      kind: 'Person · sanctioned', name: 'Viktor Branko',
      note: 'Holds 40% of Orient Star and directs Harbour Line Shipping. Two hops from the searched company. Confirm the listing with the issuing authority.' },
  };
  var CHAIN_ORDER = ['elena', 'azure', 'marina', 'nominees', 'falcon'];
  var SIDE_ORDER = ['rashid', 'orient', 'viktor'];
  var selected = 'elena';

  function nodeButton(key) {
    var n = NODES[key];
    var cls = 'node-btn' + (n.dark ? ' dark' : '') + (selected === key ? ' selected' : '');
    var badge = n.badge ? '<span class="badge ' + n.badgeClass + '" style="height:22px;padding:0 10px 0 8px;font-size:11px">' + esc(n.badge) + '</span>' : '';
    var tag = n.tag ? '<span class="mono" style="font-size:12px;font-weight:500">' + esc(n.tag) + '</span>' : '';
    return '<button type="button" class="' + cls + '" data-node="' + key + '" aria-pressed="' + (selected === key) + '">' +
      '<span class="top"><span class="title">' + esc(n.title) + '</span>' + (badge || tag) + '</span>' +
      '<span class="sub">' + esc(n.sub) + '</span></button>';
  }

  function renderOwnership() {
    var chainHtml = '';
    CHAIN_ORDER.forEach(function (key, i) {
      chainHtml += nodeButton(key);
      if (i < CHAIN_ORDER.length - 1) {
        chainHtml += '<div class="owns-line" aria-hidden="true">' + esc(NODES[CHAIN_ORDER[i + 1]].owns) + '</div>';
      }
    });
    document.getElementById('ownership-chain').innerHTML = chainHtml;

    var sideHtml = SIDE_ORDER.map(nodeButton).join('');
    var n = NODES[selected];
    sideHtml += '<div class="node-detail" aria-live="polite">' +
      '<span class="kind">' + esc(n.kind) + '</span>' +
      '<span class="name">' + esc(n.name) + '</span>' +
      '<p class="note">' + esc(n.note) + '</p></div>';
    document.getElementById('ownership-side').innerHTML = sideHtml;

    document.querySelectorAll('#ownership-chain [data-node], #ownership-side [data-node]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        selected = btn.dataset.node;
        renderOwnership();
      });
    });
  }

  if (document.getElementById('ownership-chain')) renderOwnership();

  /* ---------------- Adverse-media classification demo ---------------- */
  var OPTS = [['unreviewed', 'Unreviewed'], ['confirmed', 'Confirmed match'], ['partial', 'Partial match'], ['false', 'False match'], ['no_match', 'No match']];
  var RAW = [
    { source: 'EXAMPLE BUSINESS DAILY', date: '2025-06-14', category: 'regulatory', claim: 'A free-zone trading company with a similar name was fined by its regulator for late filings.' },
    { source: 'EXAMPLE COURT RECORDS', date: '2024-11-02', category: 'litigation', claim: 'A commercial dispute names "Falcon Capital" as defendant; the registration number is not stated.' },
  ];
  var TONE = {
    unreviewed: { label: 'Unreviewed', cls: '' },
    confirmed: { label: 'Confirmed match', cls: 'badge-high' },
    partial: { label: 'Partial match', cls: 'badge-review' },
    false: { label: 'False match', cls: 'badge-clear' },
    no_match: { label: 'No match', cls: 'badge-clear' },
  };
  var ORDER = { confirmed: 3, partial: 2, false: 1, no_match: 0 };
  var cls = RAW.map(function () { return 'unreviewed'; });

  function renderMedia() {
    var html = RAW.map(function (m, i) {
      var opts = OPTS.map(function (pair) {
        var v = pair[0], label = pair[1];
        var on = cls[i] === v;
        return '<button type="button" class="classify-btn' + (on ? ' selected' : '') +
          '" data-i="' + i + '" data-v="' + v + '" role="radio" aria-checked="' + on + '">' + esc(label) + '</button>';
      }).join('');
      return '<article class="media-finding">' +
        '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">' +
        '<span class="badge badge-review">Open-web · unverified</span>' +
        '<span class="media-source">' + esc(m.source) + ' · ' + esc(m.date) + ' · ' + esc(m.category) + '</span></div>' +
        '<p style="margin:0;font-size:16px">' + esc(m.claim) + '</p>' +
        '<div class="classify-group" role="radiogroup" aria-label="Classification">' + opts + '</div></article>';
    }).join('');
    document.getElementById('media-findings').innerHTML = html;

    var reviewed = cls.filter(function (c) { return c !== 'unreviewed'; });
    var dec = reviewed.length ? reviewed.reduce(function (a, b) { return ORDER[b] > ORDER[a] ? b : a; }) : 'unreviewed';
    var badge = document.getElementById('overall-badge');
    badge.textContent = TONE[dec].label;
    badge.className = 'badge ' + (TONE[dec].cls || 'chip-outline');

    document.querySelectorAll('.classify-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        cls[Number(btn.dataset.i)] = btn.dataset.v;
        renderMedia();
      });
    });
  }

  if (document.getElementById('media-findings')) renderMedia();
})();
