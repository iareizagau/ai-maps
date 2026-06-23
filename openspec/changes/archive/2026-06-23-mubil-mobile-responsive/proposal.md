## Why

The MUBIL platform's web interface has several layout issues, cut-off text elements, overlapping UI elements, and a completely missing mobile navigation menu on screen sizes smaller than 768px (mobile/tablet). Making the platform fully responsive is critical for EV drivers accessing charging maps, routes, and AI advice on their mobile devices.

## What Changes

- **Mobile Navigation Menu**: Add a mobile-friendly slide-over drawer or dropdown menu to `base.html` using Alpine.js to allow navigation on mobile devices.
- **Landing Page Header Banner**: Fix the top pilot banner text wrap and truncation on mobile screens in `index.html`.
- **Ask Page Header Overlap**: Increase top margins/padding on the `ask.html` page to prevent the header overlap.
- **Advisor Page FAB and Layout**: Fix the floating AI Assistant button (FAB) position/layering, and adjust spacing for cards on mobile screens in `advisor.html` and its sub-templates.
- **Infrastructure Map & Viewport**: Clean up the raw template comment rendering and ensure the charger counts and UI panels fit and display nicely within mobile viewports in `infrastructure.html`.
- **Route Page Responsiveness**: Ensure route planning panels and Leaflet map containers stack and resize correctly on mobile devices in `route.html`.

## Capabilities

### New Capabilities

*(None - this is a frontend responsiveness optimization)*

### Modified Capabilities

- `mubil-mobile-responsive`: Adapt existing frontend layouts and components in the MUBIL application to be fully responsive.

## Impact

- `src/templates/mubil/base.html`
- `src/templates/mubil/index.html`
- `src/templates/mubil/ask.html`
- `src/templates/mubil/advisor.html`
- `src/templates/mubil/infrastructure.html`
- `src/templates/mubil/route.html`
