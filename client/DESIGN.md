# EyeNED web interface — DESIGN.md

Design rules for `client/`, implementing ADR 0006 (`Eyened/designdocuments`,
`decisions/0006-web-ui-design-system.md`) with IBM's [Carbon Design System](https://www.carbondesignsystem.com/).
Values from `@carbon/themes` 11.83.0, `@carbon/type` 11.69.0 and `@carbon/styles` 1.117.0 (not installed). `src/app.css` is
the token source; change this file in the same commit as any value there.

## Overview

- Every screen is dark: Carbon Gray 100.
- Components are shadcn-svelte (bits-ui) restyled to Carbon; callers keep shadcn's props.

## Colors

Carbon [colour tokens](https://www.carbondesignsystem.com/building-blocks/foundations/color/tokens),
Gray 100. Class names are token names (`bg-layer-01`, `text-text-primary`). Tailwind's palette and
shadcn's colour names do not exist.

| Token                                                                    | Value                                                     | Use                                               |
| ------------------------------------------------------------------------ | --------------------------------------------------------- | ------------------------------------------------- |
| `background`                                                             | `#161616`                                                 | Page background                                   |
| `background-hover`                                                       | `rgba(141,141,141,0.16)`                                  | Hover on `background`                             |
| `background-active`                                                      | `rgba(141,141,141,0.4)`                                   | Pressed on `background`                           |
| `background-inverse`                                                     | `#f4f4f4`                                                 | Tooltip                                           |
| `background-selected`                                                    | `rgba(141,141,141,0.24)`                                  | Pressed search clear button                       |
| `layer-01`                                                               | `#262626`                                                 | Panels, table rows, modals                        |
| `layer-02`                                                               | `#393939`                                                 | A layer on `layer-01`                             |
| `layer-hover-01`                                                         | `#333333`                                                 | Hover on `layer-01`                               |
| `layer-hover-02`                                                         | `#474747`                                                 | Select options inside a modal                     |
| `layer-selected-01`                                                      | `#393939`                                                 | Selected dropdown item                            |
| `layer-selected-hover-01`                                                | `#474747`                                                 | Hover on a selected dropdown item                 |
| `layer-selected-inverse`                                                 | `#f4f4f4`                                                 | Table expand chevron; selected thumbnail border   |
| `layer-active-01`                                                        | `#525252`                                                 | Pressed on `layer-01`                             |
| `layer-accent-01`                                                        | `#393939`                                                 | Table header                                      |
| `field-01`                                                               | `#262626`                                                 | Input fill on `background`                        |
| `field-hover-01`                                                         | `#333333`                                                 | Input hover on `background`                       |
| `field-02`                                                               | `#393939`                                                 | Input fill on `layer-01`                          |
| `field-hover-02`                                                         | `#474747`                                                 | Input hover on `layer-01`                         |
| `border-subtle-00`                                                       | `#393939`                                                 | Dividers on `background`; progress track          |
| `border-subtle-01`                                                       | `#525252`                                                 | Dividers on `layer-01`                            |
| `border-subtle-02`                                                       | `#6f6f6f`                                                 | Open dropdown field inside a modal                |
| `border-strong-01`                                                       | `#6f6f6f`                                                 | Input border on `background`                      |
| `border-strong-02`                                                       | `#8d8d8d`                                                 | Input border on `layer-01`                        |
| `border-interactive`                                                     | `#4589ff`                                                 | Current header item, selected tab                 |
| `border-disabled`                                                        | `rgba(141,141,141,0.5)`                                   | Disabled input border                             |
| `overlay`                                                                | `rgba(0,0,0,0.6)`                                         | Behind a modal                                    |
| `skeleton-background`                                                    | `#292929`                                                 | Loading placeholder                               |
| `skeleton-element`                                                       | `#393939`                                                 | Loading placeholder shapes                        |
| `text-primary`                                                           | `#f4f4f4`                                                 | Body text, status labels                          |
| `text-secondary`                                                         | `#c6c6c6`                                                 | Secondary text, header nav                        |
| `text-helper`                                                            | `#a8a8a8`                                                 | Help text                                         |
| `text-placeholder`                                                       | `rgba(244,244,244,0.4)`                                   | Placeholders                                      |
| `text-on-color`                                                          | `#ffffff`                                                 | Text on filled buttons                            |
| `text-on-color-disabled`                                                 | `rgba(255,255,255,0.25)`                                  | Text on disabled filled buttons                   |
| `text-inverse`                                                           | `#161616`                                                 | Text on white (tertiary hover)                    |
| `text-disabled`                                                          | `rgba(244,244,244,0.25)`                                  | Disabled text                                     |
| `text-error`                                                             | `#ff8389`                                                 | Field error text                                  |
| `link-primary`                                                           | `#78a9ff`                                                 | Links, ghost button text                          |
| `link-primary-hover`                                                     | `#a6c8ff`                                                 | Link hover                                        |
| `link-secondary`                                                         | `#a6c8ff`                                                 | A link in a hovered table row                     |
| `icon-primary`                                                           | `#f4f4f4`                                                 | Icons                                             |
| `icon-secondary`                                                         | `#c6c6c6`                                                 | Less important icons                              |
| `icon-inverse`                                                           | `#161616`                                                 | Icons on white                                    |
| `icon-disabled`                                                          | `rgba(244,244,244,0.25)`                                  | Disabled icons                                    |
| `interactive`                                                            | `#4589ff`                                                 | Progress fill, selected controls                  |
| `focus`                                                                  | `#ffffff`                                                 | Focus ring                                        |
| `focus-inset`                                                            | `#161616`                                                 | Contrast ring paired with `focus`                 |
| `support-error` / `-success` / `-warning`                                | `#fa4d56` / `#42be65` / `#f1c21b`                         | Notification, validation icons; finished progress |
| `notification-background-error` / `-success` / `-warning`                | `#262626`                                                 | Notification fill                                 |
| `button-primary` / `-hover` / `-active`                                  | `#0f62fe` / `#0050e6` / `#002d9c`                         | Primary button                                    |
| `button-secondary` / `-hover` / `-active`                                | `#6f6f6f` / `#5e5e5e` / `#393939`                         | Secondary button                                  |
| `button-tertiary` / `-hover` / `-active`                                 | `#ffffff` / `#f4f4f4` / `#c6c6c6`                         | Tertiary button                                   |
| `button-danger-primary` / `button-danger-hover` / `button-danger-active` | `#da1e28` / `#b81921` / `#750e13`                         | Danger button                                     |
| `button-danger-secondary`                                                | `#fa4d56`                                                 | Danger tertiary and ghost text                    |
| `button-disabled`                                                        | `rgba(141,141,141,0.3)`                                   | Disabled filled button                            |
| `status-gray` / `-blue` / `-green` / `-red` / `-purple`                  | `#8d8d8d` / `#4589ff` / `#42be65` / `#fa4d56` / `#a56eff` | Status icons                                      |
| `content-switcher-background-hover`                                      | `rgba(141,141,141,0.12)`                                  | Content switcher hover                            |
| `content-switcher-selected`                                              | `rgba(141,141,141,0.24)`                                  | Selected content switcher option                  |

A field inside a dialog uses `field-02`, `field-hover-02`, `border-strong-02` automatically (`in-dialog:` variant in `app.css`, Carbon's Layer).

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
  (Carbon's values minus the 1 px border), Button max width and login column `max-w-80`/`w-80` (20 rem), the login logo `w-32` (its 128 px source), the header's 3 px current-item bar `0.75`, and the inline notification insets `3.25 3.5 3.75 13` (Carbon's values), the modal footer buttons `pt-3.5 pb-8`, the text area `pt-2.75`, the icon tooltip `py-0.5`, the tooltip `max-w-72`, the progress bar `min-w-12`, the table skeleton button `w-37.5` (Carbon's 150 px), the modal widths and heights (Carbon's percentages as fractions), the dropdown menu `max-h-66` (5.5 items) and inline menu `min-w-72 max-w-120` (288 / 480 px), the expanded table row `ps-14` (3.5 rem), and the pagination select `pe-9` (2.25 rem).
- Header 48 px (`h-12`), fixed; content below it (`mt-12`) in `<main class="max-w-page px-4">`,
  left-aligned with the wordmark.
- Breakpoints: Carbon's `md` 42rem, `lg` 66rem, `xlg` 82rem ([Carbon](https://www.carbondesignsystem.com/building-blocks/foundations/2x-grid/overview)); use them only where a Carbon component page specifies breakpoint behaviour (Modal). Carbon's `max` (99rem) is `max-w-page`.

## Shapes

Square corners; the radii are rounded-checkbox and rounded-tooltip (2 px each, Carbon). Shadows: `shadow-popover` for menus and popovers (Carbon tooltips have none); `shadow-button-focus` for Button focus. Motion: `animate-loading-rotate` (690 ms) for the loading spinner; `animate-skeleton` (3000 ms) for skeletons.

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
- **Text input / Password input** (`ui/text-input` over `ui/input`, `ui/label`, `ui/field`):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/text-input/guidelines).
  Carbon prop names (`labelText`, `invalidText`).
- **Checkbox** (`ui/checkbox`): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/checkbox/guidelines).
- **Notification (inline)** (`ui/inline-notification` over `ui/alert`):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/notification/guidelines).
  Low contrast only: Carbon's high-contrast default is a light box on Gray 100. Error kind only.
- **Login** (`LoginForm.svelte`): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/patterns/login); one centred column, as Carbon suggests without an illustration.
- **Data table** (`ui/table`, `size` `md` 40 px, `lg` 48 px or `xl` 64 px for two-line rows; `Table.Toolbar`, `Table.ToolbarSearch`):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/usage). Fewer than three row
  actions are inline buttons, not an overflow menu. `Table.Skeleton` is Carbon's DataTableSkeleton
  (toolbar, real headers, 5 skeleton rows, `aria-busy`), shown while a table loads. Expandable rows: `Table.ExpandButton` in the first cell and in the header (expand all), `Table.ExpandedRow` below its row; row actions are ghost buttons with a text label and icon (Claim, Unclaim, Edit) in a trailing column, whose header is an sr-only `Actions`; `Table.SkeletonRows` replaces the body while a filter or page loads. Links are `link-primary`, `link-secondary` while their row is hovered.
- **Search** (`Table.ToolbarSearch`, persistent): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/search/usage).
- **Modal** (`ui/modal` over `ui/dialog`; `danger`, sizes `xs`/`sm`): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/modal/usage).
  Submit shows Inline loading on the primary, disables the rest and blocks closing; a server error is an inline
  notification above the footer.
- **Inline loading** (`ui/inline-loading`): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/inline-loading/usage).
- **Select** (`ui/select-input` `SelectInput`/`SelectItem` over `ui/native-select`, a native `<select>`):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/select/usage). For a custom menu use Dropdown.
- **Dropdown** (`ui/dropdown` over `ui/select` (bits-ui); `type` `default` or `inline`, size lg 48 px):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/dropdown/usage). Inline in a table toolbar to
  filter it; each filter has an "All" item. Below md the toolbar's filters move behind a Filter icon button that
  opens them as default Dropdowns (Carbon puts toolbar filters in a `TableToolbarMenu`).
- **Breadcrumb** (`ui/breadcrumb`; the current page is not listed; trailing `/`):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/breadcrumb/usage).
- **Pagination** (`Table.Pagination`, directly below its table, height matching the rows; use `Table.Pagination`, not `ui/pagination`):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/pagination/usage). Narrower than 42rem it
  shows only the item range and Previous/Next (a container query, as in `@carbon/styles`).
- **Notification (inline), for page actions**: one notification above the table toolbar for failed row actions
  and reloads, no success toasts ([Carbon](https://www.carbondesignsystem.com/building-blocks/core/patterns/notifications)).
  Error kind only, so a partial claim-all ("Claimed 1 of 2 sets") deliberately shows as an error; there is no warning kind.
- **Text area** (`ui/text-area` over `ui/textarea`): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/text-input/usage).
- **Tooltip** (`ui/tooltip`) and **Icon button** (`ui/icon-button`, ghost, label = tooltip + accessible name):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/tooltip/usage).
- **Progress bar** (`ui/progress-bar` over `ui/progress`, small; `status` `active` or `finished`, finished fills the bar in
  `support-success` with a CheckmarkFilled in the label row): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/components/progress-bar/usage).
- **Empty state** (`ui/empty`, left-aligned, no image): [Carbon](https://www.carbondesignsystem.com/building-blocks/core/patterns/empty-states).
- **Status indicator** (`ui/status-indicator`; task states in `src/lib/tasks/taskStatus.ts`):
  [Carbon](https://www.carbondesignsystem.com/building-blocks/core/patterns/status-indicators).

### Deviations from Carbon

| Element             | Carbon                                                              | Ours                                               | Reason                                                 |
| ------------------- | ------------------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------ |
| Header text         | Wordmark `body-compact-01` at 600 / 0.1 px; nav 0 px letter spacing | `heading-compact-01` / `body-compact-01` (0.16 px) | Weights and spacing come only from type tokens         |
| Header user action  | Icon-only                                                           | Username as text                                   | A grader on a shared workstation sees who is logged in |
| Header nav          | Hidden below `lg`                                                   | Always shown                                       | Few items; no side nav yet                             |
| Login flow          | Two steps: username, then password or SSO                           | One step; OIDC button shown up front               | Our provider is fixed; nothing to route                |
| Field validation    | On blur                                                             | On submit; cleared once the field has text         | Blur validation flashes an error when tabbing to OIDC  |
| Filled status icons | Inner mark (`!`, `×`) filled                                        | Transparent; the background shows through          | `carbon-icons-svelte` ships the inner path unfilled    |
| Tasks table filter  | Toolbar filter menu                                                 | "Show archived" checkbox in the table toolbar      | A filter menu is deferred to a later layer             |

## Keyboard & Focus

- Every focusable element shows a 2 px `focus` ring inside its edge (checkbox: 1 px outside, as Carbon draws it). Never `outline-none` or
  `outline-hidden`.
- Buttons: `focus` border plus `shadow-button-focus`; Link (`ui/button` `variant="link"` only): 1 px `focus` outline; a plain `<a>` gets the 2 px ring.
- Modal: focus starts on the first field (danger: Cancel); while submitting, focus parks on the primary button, which is aria-disabled, not disabled.
- Pagination: Previous and Next are aria-disabled at the ends; reaching the last page moves focus to Previous, reaching page 1 to Next (Carbon React).

## Do's and Don'ts

- Token classes only; no hex, `rgb()` or named colours in components, `<style>` or `style=`.
- No arbitrary values (`p-[13px]`), no `dark:`.
- Carbon spacing steps only (see Layout).
- Status = icon + label; colour on the icon.
- One primary button per view; danger only for destructive actions.
- Button icons go after the label, at most one per button. The button pins its icon to the right
  edge, as Carbon does; there is no leading-icon variant.
- Merge classes with `cn`/`tv` from `$lib/utils`, never `tailwind-merge`/`tailwind-variants` directly.
