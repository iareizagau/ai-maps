# Capability: Mubil Mobile Responsiveness

## Purpose
Ensure all core views and layouts within the Mubil application (Landing, Advisor, Ask, Map/Infrastructure) are fully optimized, accessible, and readable across all mobile and desktop viewports.

## Requirements

### Requirement: Mobile Navigation Menu
The system SHALL display a hamburger menu icon in the header on mobile viewports (< 768px) instead of the desktop horizontal navigation links. When clicked, it SHALL display a navigation menu containing links to Advisor, Ask, Route, Mapa, Plan, and News.

#### Scenario: Opening and closing the mobile menu
- **WHEN** the user taps the hamburger icon in the mobile header
- **THEN** the mobile menu drawer/dropdown opens displaying all links, and tapping the close icon closes the menu

### Requirement: Responsive Landing Page Header
The system SHALL ensure the top pilot banner text ("Hablemos de un piloto") is fully wrapped and readable on mobile devices without any text truncation or clipping.

#### Scenario: Viewing the home page banner on mobile
- **WHEN** the home page is loaded on a screen width under 768px
- **THEN** the pilot banner text wraps and displays the full description alongside the CTA link

### Requirement: Ask Page Spacing
The system SHALL apply appropriate margin or padding at the top of the Ask page container to prevent the sticky header from overlapping any portion of the introductory text.

#### Scenario: Loading the Ask page
- **WHEN** the Ask page is viewed on any screen width
- **THEN** the top introduction text container is fully visible and not covered by the header

### Requirement: Advisor Page Spacing & FAB Layout
The system SHALL adjust card spacing and the floating AI Assistant button (FAB) layout on mobile screens to ensure the FAB does not overlap text inside the cards and card edges do not clip content.

#### Scenario: Scrolling the Advisor page on mobile
- **WHEN** the user views the Advisor page on mobile
- **THEN** the floating AI Assistant button remains usable without covering the interactive cards, and the cards have sufficient margins

### Requirement: Infrastructure Map Page Layout
The system SHALL hide raw template comments on the infrastructure map page and adjust viewport constraints so that charger counts and filters are not cut off at the bottom of the viewport.

#### Scenario: Viewing map charger counts
- **WHEN** the user visits the map page on mobile
- **THEN** no raw Django comment text is visible and the charger counts are fully visible within the container
