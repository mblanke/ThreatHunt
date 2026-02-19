# Material UI (MUI) Design System

Use this skill for any React/Next "portal/admin/dashboard" UI so you stay consistent and avoid random component soup.

## Standard choice
- Preferred UI library: **MUI (Material UI)**.
- Prefer MUI components over ad-hoc HTML/CSS unless there's a good reason.
- One design system per repo (do not mix Chakra/Ant/Bootstrap/etc.).

## Setup (Next.js/React)
- Install: `@mui/material @emotion/react @emotion/styled`
- If using icons: `@mui/icons-material`
- If using data grid: `@mui/x-data-grid` (or pro if licensed)

## Theming rules
- Define a single theme (typography, spacing, palette) and reuse everywhere.
- Use semantic colors (primary/secondary/error/warning/success/info), not hard-coded hex everywhere.
- Prefer MUI's `sx` for small styling; use `styled()` for reusable components.

## "Portal" patterns (modals, popovers, menus)
- Use MUI Dialog/Modal/Popover/Menu components instead of DIY portals.
- Accessibility requirements:
  - Focus is trapped in Dialog/Modal.
  - Escape closes modal unless explicitly prevented.
  - All inputs have labels; buttons have clear text/aria-labels.
  - Keyboard navigation works end-to-end.

## Layout conventions (for portals)
- Use: AppBar + Drawer (or NavigationRail equivalent) + main content.
- Keep pages as composition of small components: Page → Sections → Widgets.
- Keep forms consistent: FormControl + helper text + validation messages.

## Performance hygiene
- Avoid re-render storms: memoize heavy lists; use virtualization for large tables (DataGrid).
- Prefer server pagination for huge datasets.

## PR review checklist
- Theme is used (no random styling).
- Components are MUI where reasonable.
- Modal/popover accessibility is correct.
- No mixed UI libraries.
