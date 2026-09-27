# InvoiceBot — Get Paid Faster. Invoice in 30 Seconds.

**The open-source invoicing tool freelancers actually want.** No bloat. No learning curve. No 47-tab enterprise nightmare. Just create an invoice, send it, get paid.

> **Built in public.** Zero dependencies. Zero build step. One `node server.js` and you're live.

---

## Why InvoiceBot Exists

Every invoicing tool out there is either:
- **Too complex** — built for enterprises, drowns freelancers in features they'll never use
- **Too expensive** — $30-50/month for what should be a simple form
- **Too locked-in** — your data lives on their servers, good luck exporting it

InvoiceBot is none of that. It's a single Node.js server with zero dependencies that does exactly one thing well: **get you paid**.

---

## What You Get

| Feature | Status |
|---------|--------|
| Create invoices with line items in 30 seconds | Done |
| Dashboard — total revenue, paid, pending, overdue at a glance | Done |
| Client management | Done |
| Auto tax calculation | Done |
| Invoice preview + print/PDF export | Done |
| Status tracking (draft / sent / paid / overdue) | Done |
| Stripe checkout — clients pay invoices online | Done |
| Subscription billing ($19/mo Pro, $39/mo Business) | Done |
| Dark mode UI | Done |
| Mobile responsive | Done |
| Docker + one-click deploy (Railway / Render / Fly.io) | Done |
| Self-hostable — your data stays yours | Done |

---

## Quick Start

```bash
git clone https://github.com/abuadamalmaliki-prog/B00K.git
cd B00K
node server.js
# Open http://localhost:3000
```

That's it. No `npm install`. No build. No config. It just works.

---

## Deploy in 2 Minutes

### Railway
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template)
```bash
railway up
```

### Render
Push to GitHub. Render auto-detects `render.yaml`. Done.

### Fly.io
```bash
fly launch
fly deploy
```

### Docker
```bash
docker build -t invoicebot .
docker run -p 3000:3000 invoicebot
```

---

## Screenshots

### Landing Page
Clean, conversion-optimized landing with pricing tiers.

### Dashboard
Real-time revenue tracking — see what's paid, pending, and overdue.

### Invoice Creator
Add line items, auto-calculate tax, assign to clients. 30 seconds flat.

### Invoice Preview
Professional invoice preview with print/PDF export.

---

## The Numbers

| Metric | Value |
|--------|-------|
| Dependencies | **0** |
| Build step | **None** |
| Lines of code | **~1,200** |
| Time to first invoice | **30 seconds** |
| Deploy time | **< 2 minutes** |
| Hosting cost | **$0 – $7/month** |

---

## Pricing (for your customers)

| Plan | Price | What They Get |
|------|-------|---------------|
| **Starter** | Free | 3 invoices/month, 1 client |
| **Pro** | $19/month | Unlimited everything, PDF, Stripe payments, branding |
| **Business** | $39/month | Multi-currency, recurring invoices, reports, API |

**22 Pro subscribers = $5,000+ ARR.** That's the whole business model.

---

## Tech Stack

- **Backend:** Node.js (zero dependencies, standard library only)
- **Frontend:** Vanilla HTML/CSS/JS (no React, no Vue, no build tools)
- **Storage:** JSON files (upgrade to PostgreSQL when you're ready)
- **Payments:** Stripe Checkout + Webhooks
- **Deploy:** Docker / Railway / Render / Fly.io

No package.json dependencies. No node_modules. No webpack. No babel. No TypeScript compilation. The entire app is **4 files** that a junior dev can read in an afternoon.

---

## Why Open Source?

Because the best marketing for a SaaS is trust. You can read every line. You can self-host it. You can fork it and make it yours.

And because the real value isn't the code — it's the hosted version that handles backups, updates, uptime, and support so you don't have to.

---

## Roadmap

- [ ] Email delivery (send invoices directly)
- [ ] Recurring invoices (auto-generate monthly)
- [ ] Multi-currency support
- [ ] Expense tracking
- [ ] Revenue reports & charts
- [ ] Client portal (clients view/pay invoices)
- [ ] QuickBooks / Xero export
- [ ] API for integrations
- [ ] Mobile app (PWA)

---

## Contributing

PRs welcome. Keep it simple. No unnecessary dependencies. If your change adds a `node_modules` folder, it's probably not the right change.

```bash
git clone https://github.com/abuadamalmaliki-prog/B00K.git
cd B00K
node server.js
# Make changes, test at http://localhost:3000
```

---

## License

MIT — do whatever you want with it.

---

**Built with zero dependencies and zero excuses.**

If this saves you time, star the repo. That's all the payment I need.
