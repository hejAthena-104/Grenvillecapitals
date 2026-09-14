# Demo labels — disabled checklist

The visible demo labels listed here have been commented out. This file now acts
as the checklist for the places that were labelled, so the labels can be restored
or audited later without hunting through the project.

_Last updated: 2026-09-14._

## 1. Prominent banner — deposit screen only, commented out

A full-width call-out (`.gc-demo-banner`) reading
**"Demo mode — no real money … Deposits here add simulated funds to your balance
instantly."**

| Page | File |
|---|---|
| Add funds / deposit | `backend/templates/dashboard/deposits.html` |

> The old two-step deposit + wallet page (`payment.html`) was removed, so there
> is no separate "send money here" screen to label.

## 2. Small inline label — withdraw & transfer screens, commented out

A pill (`.gc-demo-note`) next to the submit button reading
**"Demo · simulated transfer — no real funds move."**

| Screen | File | Placement |
|---|---|---|
| Bank withdrawal form | `backend/templates/dashboard/withdraw-funds.html` | Under "Complete withdrawal" |
| Transfers — Local (bank) | `backend/templates/dashboard/transfer.html` | Under the Local "Send Transfer" |
| Transfers — International (wire/PayPal/Wise/Cash App/Other) | `backend/templates/dashboard/transfer.html` | Above the international method forms (covers all of them) |

> The internal user-to-user page (`transfer-funds.html`) is a same-platform
> demo-balance move; it is covered by the site-wide footer line below and can
> get its own pill on request.

## 3. Footer line — site-wide, commented out

**"Demo banking platform — not a real bank; no real funds are held or moved."**

| Surface | File(s) |
|---|---|
| Dashboard footer (all logged-in pages) | `backend/templates/base_dashboard.html` (`.gc-demo-footer`) |
| All 23 marketing pages | each `frontend/**/index.html` footer copyright line |
| All outbound emails | `backend/templates/emails/base_email.html` footer |

> `frontend/offline/index.html` is a standalone offline fallback with no footer —
> intentionally not labelled.

## Styles
`.gc-demo-banner`, `.gc-demo-note`, `.gc-demo-footer` live in
`backend/static/css/grenville-theme.css`.

## Did I miss a page?
If any money-related screen shows no demo label, name it and it will be added.
