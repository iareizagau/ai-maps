# Design: Mubil Mobile Responsiveness

## Context
The eStrata/Mubil platform (Django, Tailwind 3+, Alpine.js) lacks optimization for mobile viewports. The navigation menu is absent on small screens, headers overlap content, cards feel cramped, and the floating AI Assistant button (FAB) covers critical form controls/labels when scrolled.

## Goals / Non-Goals

**Goals:**
- Implement a responsive, Alpine.js-powered mobile navigation dropdown in `base.html`.
- Prevent header overlap with content on the Ask page (`ask.html`).
- Prevent the FAB from overlapping input elements and card summaries by increasing bottom padding on the main sections.
- Solve layout constraints on narrow viewports for confirmed vehicles.
- Fix broken template multi-line comments that render as text.

**Non-Goals:**
- Full redesign of desktop navigation or dashboard layout.
- Implementation of new features in the AI Assistant or Advisor.

## Decisions

### 1. Alpine.js Responsive Mobile Menu
- **Option A:** Vanilla CSS dropdown toggle.
- **Option B (Chosen):** Alpine.js state (`mobileMenuOpen`) with transition attributes. This integrates natively with eStrata's Alpine.js setup and allows smooth dropdown transitions (`x-transition`).

### 2. Preventing Header-Content Overlaps
- **Decision:** Add extra `pt-16` on mobile screens to the main content section (`ask.html`), matching the header height (`h-14` / `h-16`) to push content clean of the sticky header.

### 3. Layout Spacing and FAB Overlap
- **Decision:** Increase padding-bottom (`pb-28 md:pb-12`) on the main container section in `advisor.html` and other templates where the FAB is used, allowing the page to scroll far enough to keep interactive cards clear of the floating button.
- **Decision:** Adjustconfirmed cards spacing/gaps (`p-4 sm:p-5`, `gap-4 sm:gap-6`) to give elements breathing room.

## Risks / Trade-offs

- **Risk:** FOUC (Flash of Unstyled Content) for hidden Alpine.js panels.
  - *Mitigation:* Added `[x-cloak] { display: none !important; }` style globally in `base.html` head.
