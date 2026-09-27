# Contributing to InvoiceBot

Thanks for wanting to help! InvoiceBot is built to stay simple. Here's how to contribute.

## Ground Rules

1. **Zero dependencies.** If your PR adds `node_modules`, it won't be merged. We use Node.js standard library only.
2. **No build step.** No webpack, no babel, no TypeScript. Vanilla JS that runs directly.
3. **Keep it simple.** If a junior dev can't read your code in 5 minutes, simplify it.

## Getting Started

```bash
git clone https://github.com/abuadamalmaliki-prog/B00K.git
cd B00K
node server.js
# Open http://localhost:3000
```

## What to Work On

Check the [issues labeled "help wanted"](https://github.com/abuadamalmaliki-prog/B00K/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) or ["good first issue"](https://github.com/abuadamalmaliki-prog/B00K/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

High-impact areas:
- Email delivery (Issue #2)
- PostgreSQL adapter (Issue #7)
- Client portal (Issue #5)
- PWA support (Issue #8)

## Pull Request Process

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Test at `http://localhost:3000`
5. Submit a PR with a clear description of what and why

## Code Style

- 2-space indentation
- Single quotes for strings
- No semicolons (just kidding, use them)
- Descriptive variable names over comments
- Functions under 30 lines

## Questions?

Open an issue. We're friendly.
