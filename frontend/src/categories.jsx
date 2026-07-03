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
  LOAN_PAYMENTS: "Other",
  TRANSFER_OUT: "Other",
  TRANSFER_IN: "Other",
  INCOME: "Other",
  GENERAL_SERVICES: "Other",
  GOVERNMENT_AND_NON_PROFIT: "Other",
  HOME_IMPROVEMENT: "Shopping",
  TRAVEL: "Transport",
  OTHER: "Other",
  BANK_FEES: "Other",
}

// Mark colors validated for colorblind separation on light + dark surfaces
// (identity is never color-alone: every use pairs the color with a label/icon).
export const CAT = {
  Groceries:     { color: "#22c55e" },
  Dining:        { color: "#ef4444" },
  Transport:     { color: "#3b82f6" },
  Shopping:      { color: "#d946ef" },
  Utilities:     { color: "#b45309" },
  Entertainment: { color: "#f59e0b" },
  Health:        { color: "#10b981" },
  Other:         { color: "#9ca3af" },
}

// Categories a user can pick when correcting a transaction (display names).
export const EDITABLE_CATEGORIES = [
  "Dining", "Groceries", "Transport", "Shopping", "Utilities",
  "Entertainment", "Health", "Travel", "Income", "Transfer", "Other",
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
  Other: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
    </svg>
  ),
}
