# EyeNED web interface — DESIGN.md

Design rules for `client/`, implementing ADR 0006 (`Eyened/designdocuments`,
`decisions/0006-web-ui-design-system.md`) with IBM's [Carbon Design System](https://www.carbondesignsystem.com/).
Values from `@carbon/themes` 11.83.0 and `@carbon/type` 11.69.0 (not installed). `src/app.css` is
the token source; change this file in the same commit as any value there.

## Overview

- Every screen is dark: Carbon Gray 100.
- Components are shadcn-svelte (bits-ui) restyled to Carbon; callers keep shadcn's props.

## Colors

Carbon [colour tokens](https://www.carbondesignsystem.com/building-blocks/foundations/color/tokens),
Gray 100. Class names are token names (`bg-layer-01`, `text-text-primary`). Tailwind's palette and
shadcn's colour names do not exist.

| Token                                                                    | Value                                         | Use                                   |
| ------------------------------------------------------------------------ | --------------------------------------------- | ------------------------------------- |
| `background`                                                             | `#161616`                                     | Page background                       |
| `background-hover`                                                       | `rgba(141,141,141,0.16)`                      | Hover on `background`                 |
| `background-active`                                                      | `rgba(141,141,141,0.4)`                       | Pressed on `background`               |
| `layer-01`                                                               | `#262626`                                     | Panels, table rows, modals            |
| `layer-02`                                                               | `#393939`                                     | A layer on `layer-01`; progress track |
| `layer-hover-01`                                                         | `#333333`                                     | Hover on `layer-01`                   |
| `layer-active-01`                                                        | `#525252`                                     | Pressed on `layer-01`                 |
| `layer-accent-01`                                                        | `#393939`                                     | Table header                          |
| `field-01`                                                               | `#262626`                                     | Input fill on `background`            |
| `field-hover-01`                                                         | `#333333`                                     | Input hover on `background`           |
| `field-02`                                                               | `#393939`                                     | Input fill on `layer-01`              |
| `field-hover-02`                                                         | `#474747`                                     | Input hover on `layer-01`             |
| `border-subtle-00`                                                       | `#393939`                                     | Dividers on `background`              |
| `border-subtle-01`                                                       | `#525252`                                     | Dividers on `layer-01`                |
| `border-strong-01`                                                       | `#6f6f6f`                                     | Input border on `background`          |
| `border-strong-02`                                                       | `#8d8d8d`                                     | Input border on `layer-01`            |
| `border-interactive`                                                     | `#4589ff`                                     | Current header item, selected tab     |
| `border-disabled`                                                        | `rgba(141,141,141,0.5)`                       | Disabled input border                 |
| `overlay`                                                                | `rgba(0,0,0,0.6)`                             | Behind a modal                        |
| `skeleton-background`                                                    | `#292929`                                     | Loading placeholder                   |
| `skeleton-element`                                                       | `#393939`                                     | Loading placeholder shapes            |
| `text-primary`                                                           | `#f4f4f4`                                     | Body text, status labels              |
| `text-secondary`                                                         | `#c6c6c6`                                     | Secondary text, header nav            |
| `text-helper`                                                            | `#a8a8a8`                                     | Help text                             |
| `text-placeholder`                                                       | `rgba(244,244,244,0.4)`                       | Placeholders                          |
| `text-on-color`                                                          | `#ffffff`                                     | Text on filled buttons                |
| `text-on-color-disabled`                                                 | `rgba(255,255,255,0.25)`                      | Text on disabled filled buttons       |
| `text-inverse`                                                           | `#161616`                                     | Text on white (tertiary hover)        |
| `text-disabled`                                                          | `rgba(244,244,244,0.25)`                      | Disabled text                         |
| `text-error`                                                             | `#ff8389`                                     | Field error text                      |
| `link-primary`                                                           | `#78a9ff`                                     | Links, ghost button text              |
| `link-primary-hover`                                                     | `#a6c8ff`                                     | Link hover                            |
| `icon-primary`                                                           | `#f4f4f4`                                     | Icons                                 |
| `icon-secondary`                                                         | `#c6c6c6`                                     | Less important icons                  |
| `icon-inverse`                                                           | `#161616`                                     | Icons on white                        |
| `icon-disabled`                                                          | `rgba(244,244,244,0.25)`                      | Disabled icons                        |
| `interactive`                                                            | `#4589ff`                                     | Progress fill, selected controls      |
| `focus`                                                                  | `#ffffff`                                     | Focus ring                            |
| `focus-inset`                                                            | `#161616`                                     | Contrast ring paired with `focus`     |
| `support-error` / `-success` / `-warning`                                | `#fa4d56` / `#42be65` / `#f1c21b`             | Notification and validation icons     |
| `notification-background-error` / `-success` / `-warning`                | `#262626`                                     | Notification fill                     |
| `button-primary` / `-hover` / `-active`                                  | `#0f62fe` / `#0050e6` / `#002d9c`             | Primary button                        |
| `button-secondary` / `-hover` / `-active`                                | `#6f6f6f` / `#5e5e5e` / `#393939`             | Secondary button                      |
| `button-tertiary` / `-hover` / `-active`                                 | `#ffffff` / `#f4f4f4` / `#c6c6c6`             | Tertiary button                       |
| `button-danger-primary` / `button-danger-hover` / `button-danger-active` | `#da1e28` / `#b81921` / `#750e13`             | Danger button                         |
| `button-danger-secondary`                                                | `#fa4d56`                                     | Danger tertiary and ghost text        |
| `button-disabled`                                                        | `rgba(141,141,141,0.3)`                       | Disabled filled button                |
| `status-gray` / `-blue` / `-green` / `-red`                              | `#8d8d8d` / `#4589ff` / `#42be65` / `#fa4d56` | Status icons                          |
| `content-switcher-background-hover`                                      | `rgba(141,141,141,0.12)`                      | Content switcher hover                |
| `content-switcher-selected`                                              | `rgba(141,141,141,0.24)`                      | Selected content switcher option      |

A field on `layer-01` (modal, table row) uses `field-02`, `field-hover-02`, `border-strong-02`.

## Typography

IBM Plex Sans (variable), self-hosted via `@fontsource-variable/ibm-plex-sans`. Carbon
[productive type set](https://www.carbondesignsystem.com/building-blocks/foundations/typography/type-sets);
one class sets size, line height, letter spacing and weight (`text-body-compact-01`).

| Token                | Size / line height | Weight | Letter spacing | Use                                 |
| -------------------- | ------------------ | ------ | -------------- | ----------------------------------- |
| `label-01`           | 12 / 16 px         | 400    | 0.32 px        | Field labels, table meta, IDs       |
| `helper-text-01`     | 12 / 16 px         | 400    | 0.32 px        | Help and error text                 |
| `body-compact-01`    | 14 / 18 px         | 400    | 0.16 px        | Default text, table cells, controls |
| `body-01`            | 14 / 20 px         | 400    | 0.16 px        | Multi-line text                     |
| `heading-compact-01` | 14 / 18 px         | 600    | 0.16 px        | Table headers, product name         |
| `heading-compact-02` | 16 / 22 px         | 600    | 0              | Section headings                    |
| `heading-03`         | 20 / 28 px         | 400    | 0              | Modal titles, login title           |
| `heading-04`         | 28 / 36 px         | 400    | 0              | Page heading                        |

## Layout

- Spacing: Carbon's [scale](https://www.carbondesignsystem.com/building-blocks/foundations/spacing/overview)
  only — `0.5 1 2 3 4 6 8 10 12 16 20 24 40`. Exceptions: Button padding `1.5 2.5 3.5 3.75 15.75`
  (Carbon's values minus the 1 px border), Button max width `max-w-80` (20 rem) and the header's 3 px current-item bar `0.75`.
- Header 48 px (`h-12`), fixed; content below it (`mt-12`) in `<main class="max-w-page px-4">`,
  left-aligned with the wordmark.
- No breakpoints.

## Shapes

Square corners (no radius classes). Shadows: `shadow-popover` for menus, popovers, tooltips;
`shadow-button-focus` for Button focus.

## Components

| shadcn `variant` | Carbon kind |     | shadcn `size` | Carbon size      |
| ---------------- | ----------- | --- | ------------- | ---------------- |
| `default`        | primary     |     | `sm`          | 32 px            |
| `secondary`      | secondary   |     | `default`     | md, 40 px        |
| `outline`        | tertiary    |     | `lg`          | 48 px            |
| `ghost`          | ghost       |     | `icon`        | icon-only, 40 px |
| `destructive`    | danger      |     |               |                  |
| `link`           | Link        |     |               |                  |

- **UI shell header** (`TopMenu.svelte`): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/ui-shell-header/guidelines),
  [Global header](https://www.carbondesignsystem.com/building-blocks/core/patterns/global-header).
- **Button** (`ui/button`): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/button/guidelines).
- **Link** (`ui/button` `variant="link"`, or `<a>` with `text-link-primary hover:text-link-primary-hover`):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/link/guidelines).

### Deviations from Carbon

| Element            | Carbon                                                              | Ours                                               | Reason                                                 |
| ------------------ | ------------------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------ |
| Header text        | Wordmark `body-compact-01` at 600 / 0.1 px; nav 0 px letter spacing | `heading-compact-01` / `body-compact-01` (0.16 px) | Weights and spacing come only from type tokens         |
| Header user action | Icon-only                                                           | Username as text                                   | A grader on a shared workstation sees who is logged in |
| Header nav         | Hidden below `lg`                                                   | Always shown                                       | No breakpoints; desktop use                            |

## Keyboard & Focus

- Every focusable element shows a 2 px `focus` ring inside its edge. Never `outline-none` or
  `outline-hidden`.
- Buttons: `focus` border plus `shadow-button-focus`; Link (`ui/button` `variant="link"` only): 1 px `focus` outline; a plain `<a>` gets the 2 px ring.

## Do's and Don'ts

- Token classes only; no hex, `rgb()` or named colours in components, `<style>` or `style=`.
- No arbitrary values (`p-[13px]`), no `dark:`.
- Carbon spacing steps only (see Layout).
- Status = icon + label; colour on the icon.
- One primary button per view; danger only for destructive actions.
- Button icons go after the label.
- Merge classes with `cn`/`tv` from `$lib/utils`, never `tailwind-merge`/`tailwind-variants` directly.
