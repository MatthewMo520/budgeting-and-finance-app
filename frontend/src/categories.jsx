// Maps Plaid primary category strings → display name
export const PLAID_TO_DISPLAY = {
  FOOD_AND_DRINK: "Dining",
  GROCERIES: "Groceries",
  TRANSPORTATION: "Transport",
  GENERAL_MERCHANDISE: "Shopping",
  RENT_AND_UTILITIES: "Utilities",
  ENTERTAINMENT: "Entertainment",
  PERSONAL_CARE: "Health",
  MEDICAL: "Health",
  LOAN_PAYMENTS: "Payments",
  TRANSFER_OUT: "Transfer",
  TRANSFER_IN: "Transfer",
  INCOME: "Income",
  GENERAL_SERVICES: "Other",
  GOVERNMENT_AND_NON_PROFIT: "Other",
  HOME_IMPROVEMENT: "Shopping",
  TRAVEL: "Transport",
  OTHER: "Other",
  BANK_FEES: "Other",
}

// Mark colors come from the theme (--cat-* tokens in index.css) so they adapt
// to light/dark automatically. Values are validated for colorblind separation
// on both surfaces (identity is never color-alone: every use pairs the color
// with a label/icon).
export const CAT = {
  Groceries:     { color: "var(--cat-groceries)" },
  Dining:        { color: "var(--cat-dining)" },
  Transport:     { color: "var(--cat-transport)" },
  Shopping:      { color: "var(--cat-shopping)" },
  Utilities:     { color: "var(--cat-utilities)" },
  Entertainment: { color: "var(--cat-entertainment)" },
  Health:        { color: "var(--cat-health)" },
  Payments:      { color: "var(--cat-payments)" },
  Transfer:      { color: "var(--cat-transfer)" },
  Income:        { color: "var(--cat-income)" },
  Other:         { color: "var(--cat-other)" },
}

// Display categories that do NOT count as spending: card payments and
// transfers move money between the user's own accounts (the underlying
// purchases are already logged), and income isn't an outflow at all.
export const NON_SPEND = new Set(["Payments", "Transfer", "Income"])

// True when a transaction should count toward spend totals/charts.
export function isSpend(t) {
  return t.amount > 0 && !NON_SPEND.has(displayCat(t.ml_category))
}

// Categories a user can pick when correcting a transaction (display names).
export const EDITABLE_CATEGORIES = [
  "Dining", "Groceries", "Transport", "Shopping", "Utilities",
  "Entertainment", "Health", "Travel", "Income", "Transfer", "Payments", "Other",
]

export function displayCat(mlCategory) {
  if (!mlCategory) return "Other"
  const mapped = PLAID_TO_DISPLAY[mlCategory.toUpperCase()]
  if (mapped) return mapped
  // Unknown label: render it Title Cased (lowercase first so ALL-CAPS isn't kept).
  return mlCategory.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

export function catStyle(mlCategory) {
  const name = displayCat(mlCategory)
  const { color } = CAT[name] || CAT.Other
  // Tinted chip background derived from the mark color — adapts to dark mode.
  return { color, bg: `color-mix(in srgb, ${color} 14%, transparent)` }
}

// SVG icons per category
export const ICONS = {
  Groceries: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
    </svg>
  ),
  Dining: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/>
      <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3zm0 0v7"/>
    </svg>
  ),
  Transport: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="3" width="15" height="13" rx="2"/>
      <path d="M16 8h4l3 5v3h-7V8z"/>
      <circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>
    </svg>
  ),
  Shopping: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
      <line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/>
    </svg>
  ),
  Utilities: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>
    </svg>
  ),
  Entertainment: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
    </svg>
  ),
  Health: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
    </svg>
  ),
  Payments: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/>
    </svg>
  ),
  Transfer: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/>
      <polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>
    </svg>
  ),
  Income: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
    </svg>
  ),
  Other: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
    </svg>
  ),
}
