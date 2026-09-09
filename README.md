# UPI Fraud Awareness Assistant

HCL Jigsaw · Edition 7 · Grade 9 "AI Revolution & Digital Futures" team project.

A chatbot that helps someone describe a suspicious UPI call, message, payment request, or QR code, and find out whether it's a scam before they lose money.

## What's in here

| Deliverable | Where |
|---|---|
| **Filled team worksheet** (all 10 questions: research, interviews template, chatbot flow design, message scripts, testing plan, pitch) | [`worksheet/UPI_Fraud_Awareness_Assistant_Team_Worksheet_FILLED.pptx`](worksheet/UPI_Fraud_Awareness_Assistant_Team_Worksheet_FILLED.pptx) |
| **Working chatbot prototype** — covers all 5 fraud scenarios from the worksheet | [`chatbot/index.html`](chatbot/index.html) · **live: [upi-suraksha-mitra.onrender.com](https://upi-suraksha-mitra.onrender.com)** |
| **WhatsApp safety poster** | [`poster/upi-safety-poster.png`](poster/upi-safety-poster.png) (source: [`poster/poster-source.html`](poster/poster-source.html)) |

## The 5 fraud scenarios covered

1. Fake "Collect Request" scam (OLX/Marketplace-style)
2. Screen-sharing / remote-access app scam (AnyDesk, TeamViewer)
3. QR code scam
4. Fake KYC / account-block phishing
5. Fake customer-care number scam

Full research, red flags, and sources are in the worksheet (Q1).

## Still needs your team

Two questions in the worksheet need real people, not research — that's the point of them:

- **Q3** — talk to 2 real people about their UPI experiences. The worksheet has a template to fill in; it's intentionally left blank.
- **Q9** — the testing plan is written, but running it with 5 real people over a few days is on your team. Use the live chatbot link above.

## Running the chatbot locally

It's a single static HTML file with no build step and no external services — open `chatbot/index.html` in any browser, or use the live link.

## Hosting

The live link is a Render static site, auto-deploying `chatbot/` from this branch on every push — no separate deploy step needed.
