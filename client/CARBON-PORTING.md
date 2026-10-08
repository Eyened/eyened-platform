# Porting a screen to Carbon

How to move one `client/` screen to the Carbon design system. The rules themselves are in
`DESIGN.md`; this file is the procedure, the traps found so far, and the known problems on the
screens still to port. Each layer adds the traps it finds and removes the problems it fixes, in
its own PR. The last layer deletes this file.

## Steps

Run in the worktree `eyened-platform-worktrees/client-carbon`, from `client/` unless noted.

1. Start the layer: `gh stack add ui/carbon-<n>-<screen>`.
2. Write down, before editing:
    - **File set:** the route files plus the `$lib` files they import transitively, minus named
      exclusions (files that belong to a later layer).
    - **Behaviour checklist:** one line per v1 behaviour of the screen, from the current code.
    - **Other importers:** for each `ui/` component the layer restyles,
      `git grep -l 'components/ui/<name>' -- src`, minus the file set.
3. Restyle. Check each component against
   `https://www.carbondesignsystem.com/building-blocks/core/components/<slug>/guidelines` (and its
   Style and Accessibility tabs) and each pattern against
   `https://www.carbondesignsystem.com/building-blocks/core/patterns/<slug>`. A deviation needs a
   reason and a `DESIGN.md` row.
4. Run the gates (CI does not run on stacked PRs):
   `npm run verify:runes && npm run lint && npm run check && npm run test && npm run build`
5. Run the old-token check below over the file set; it must print nothing.
6. Demo on the dev stack: recreate only the `client` service with the worktree's `client/`
   mounted; the database, server and storage mounts stay as they are. From the main checkout's
   `deploy/`, with an override file outside the repo:

    ```sh
    cat > ../../eyened-platform-worktrees/client-carbon.override.yaml <<'YAML'
    services:
      client:
        volumes:
          - /home/kdatta/workspace/eyened-platform-worktrees/client-carbon/client:/app/client:z
          - client_node_modules:/app/client/node_modules
    YAML
    docker compose -f compose.yaml -f compose.dev.yaml -f compose.storage.yaml \
      -f compose.host-ports.yaml -f ../../eyened-platform-worktrees/client-carbon.override.yaml up -d client
    ```

    The entrypoint reinstalls `node_modules` when the lockfile differs. Open `http://localhost:17000`.
    When done, give `.svelte-kit` back to your user, then restore the main checkout's client:

    ```sh
    docker exec eyened-dev-kaustav-client-1 chown -R "$(id -u):$(id -g)" /app/client/.svelte-kit
    docker compose -f compose.yaml -f compose.dev.yaml -f compose.storage.yaml \
      -f compose.host-ports.yaml up -d client
    ```

7. On the demo: tick the behaviour checklist; open each other importer's screen and check it
   still works.
8. Open the PR with `gh stack submit`. The body has:
    - the behaviour checklist;
    - the Carbon conformance table (Element · Carbon page · Result). The Result cell names the
      values compared, for example "✓ 40 px rows; header `layer-accent-01`; Tab/Enter";
    - the other importers checked;
    - what still looks unstyled and why.
9. In the same PR: `DESIGN.md` entries for each component touched, and this file updated.
10. A review fix is a new commit on its own branch, then `gh stack rebase` and `gh stack push`.
    Never merge into a stack branch; never use GitHub's Merge button.

## Old-token check

Put the file set in `FILES`, then run each pattern. The `-e` matters: one pattern starts with
`-`. Use `[[:space:]]`, not `\s` — inside a bracket in `git grep -E`, `\s` matches nothing.

```sh
FILES="src/routes/<screen> src/lib/<…>"   # *.svelte, *.ts, *.css only

# shadcn colour utilities (Carbon names like text-text-primary pass)
git grep -nE -e '(^|[[:space:]"'"'"'{:])(bg|text|border|ring|outline|fill|stroke|divide|placeholder)-(input|ring|foreground|primary|secondary|muted|accent|destructive|card|popover|sidebar|chart)\b' -- $FILES
git grep -nE -e 'border-border([[:space:]"'"'"'}/]|$)' -- $FILES

# Tailwind default palette
git grep -nE -e '(^|[[:space:]"'"'"'{:])(bg|text|border|ring|outline|fill|stroke|divide)-(white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)\b' -- $FILES

# Tailwind default type, weight, radius, shadow, width, outline removal
git grep -nE -e '(^|[[:space:]"'"'"'{:])(text-(xs|sm|base|lg|[2-9]?xl)|font-(thin|extralight|light|normal|medium|semibold|bold|extrabold|black)|rounded(-(xs|sm|md|lg|xl|[2-4]xl))?|shadow(-(2xs|xs|sm|md|lg|xl|2xl))?|max-w-(xs|sm|md|lg|xl|[2-7]xl)|outline-(none|hidden))([[:space:]"'"'"'}]|$)' -- $FILES

# Breakpoint prefixes (tv size keys like `sm: "…"` pass)
git grep -nE -e '(^|[[:space:]"'"'"'{])(sm|md|lg|xl|2xl):[a-z-]' -- $FILES

# Colour literals, fonts and old variables in <style> blocks and style= attributes
git grep -nE -e '#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|font-family|var\(--(background|foreground|popover|muted|border|input|ring|primary|secondary|accent|destructive|card|sidebar|chart)' -- $FILES ':!src/app.css'

# dark: variants, and arbitrary values (data-[state=open]: and has-[>svg]: pass)
git grep -nE -e 'dark:' -e '-\[[^]]*\]([^:]|$)' -- $FILES
```

## Traps

| Trap                                                                                                                                   | What to do                                                                                                            |
| -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| An unknown class (`bg-primary`, `text-sm`, `p-[13px]`) generates no CSS and no error                                                   | Only the old-token check catches it                                                                                   |
| tailwind-merge reads `text-<carbon type token>` as a colour and drops it when a colour class follows                                   | Use `cn` from `$lib/utils` and the configured `tv`; a new or regenerated `tv()` file imports the configured one       |
| Tailwind emits only theme variables a class references                                                                                 | Write class names in full (`"text-status-gray"`), never `` `text-status-${x}` ``                                      |
| `--spacing` must stay: `tw-animate-css` and `calendar.svelte` call `--spacing()`                                                       | Use only Carbon's steps: `0.5 1 2 3 4 6 8 10 12 16 20 24 40`                                                          |
| A bare `border` draws in `currentColor` (Tailwind v4), so it is as bright as the text                                                  | Always pair it with a border token: `border border-border-subtle-01`                                                  |
| Colours in `<style>` blocks and `style=` attributes bypass the theme; v1 used black-on-white `rgba(0,0,0,…)`, invisible on Gray 100    | Replace with `var(--color-<token>)` or a class                                                                        |
| Svelte component CSS is unlayered and beats Tailwind's base layer; a route's `:global(body)` stays loaded after client-side navigation | No `:global(body)` font or colour; layout-only rules stay                                                             |
| `outline-none` / `outline-hidden` cancel the focus ring                                                                                | Drop them when restyling; buttons use Carbon's button focus                                                           |
| A field on `layer-01` (modal, table row) is the same colour as `field-01` and vanishes                                                 | Use the 02 set: `field-02`, `field-hover-02`, `border-strong-02`                                                      |
| Tertiary button hover fills white                                                                                                      | Text and icon become `text-inverse` / `icon-inverse`                                                                  |
| Status text in a status colour fails 4.5:1 on a hovered row                                                                            | Colour goes on the icon; the label is `text-primary`                                                                  |
| Restyling a shared `ui/` component changes unconverted screens                                                                         | Smoke-check other importers; when the Carbon element differs (content switcher vs button group), make a new component |
| Tests query by role and name; a button that becomes a tab, or an enum shown as a label, breaks them                                    | Update the selector in the same commit, same intent                                                                   |
| `svelte-sonner` removes every toast after 4 s                                                                                          | Error toasts pass `{ duration: Number.POSITIVE_INFINITY }`                                                            |
| CI runs only on PRs into `development`/`main`, so only on PR 0                                                                         | Layers 1+ run the gates locally (step 4)                                                                              |
| A theme change re-sorts classes in files nobody touched: `prettier-plugin-tailwindcss` puts classes it does not know first             | Run `npx prettier --write .` and commit the re-sort on its own; check it with the token check in the P0 plan          |
| The demo container runs as root and writes `.svelte-kit` into the worktree; `npm run check` then fails with EACCES                     | `chown` it back through `docker exec` (step 6) — never `rm` it                                                        |
| A caller puts an icon before the label                                                                                                 | Carbon puts it after; move it when the caller's screen is ported                                                      |
| `docs/superpowers/` (specs, plans) is gitignored, so it is not in the worktree                                                         | Pass the main checkout's path to agents working in the worktree                                                       |

## Known problems on screens still to port

| File                                                                                                    | Problem after PR 0                                                                                                 | Layer                                       |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| `src/lib/Dialogue.svelte`                                                                               | `var(--popover)`, `var(--popover-foreground)`: the segmentation dialogue over the image is transparent             | Viewer                                      |
| `src/lib/viewer-window/BrowserOverlay.svelte`                                                           | `var(--background)`, `var(--border)`, `.browser-light-surface` (class removed)                                     | Viewer                                      |
| `src/lib/browser/BrowserPicker.svelte`                                                                  | `var(--background)`, `var(--border)`, `.browser-light-surface` (class removed)                                     | Browser                                     |
| `src/lib/forms/SchemaForm.svelte`                                                                       | `hsl(var(--muted))` (was already invalid on oklch values)                                                          | Viewer forms                                |
| `src/lib/viewer-window/ViewerWindowLoader.svelte`                                                       | Adds and removes `dark` on `<html>`; the class no longer means anything                                            | Viewer                                      |
| `src/routes/+layout.svelte`                                                                             | Body keeps `height: 100vh`, flex column, `overflow: hidden` for the viewer's `flex: 1` chain (`MainViewer.svelte`) | Viewer: move to the viewer root if possible |
| `src/lib/tasks/TaskPanel.svelte`                                                                        | `ui/button-group`; black/white `rgba(…)` in `<style>`; `outline` buttons                                           | Viewer                                      |
| `src/lib/browser/AdvancedFilters.svelte`                                                                | shadcn colour classes                                                                                              | Browser                                     |
| `src/lib/browser/Browser.svelte`, `src/lib/components/FeaturesTable.svelte`                             | `variant="link"` callers (the second typed through `renderComponent`); the variant stays, mapped to Link classes   | —                                           |
| `src/lib/components/ui/calendar/calendar.svelte`                                                        | `[--cell-size:--spacing(8)]` fails the arbitrary-value check                                                       | Whichever layer first uses the calendar     |
| `src/lib/Popup.svelte`, `src/lib/browser/SeriesComponent.svelte`, `src/lib/browser/ExternalData.svelte` | White / `--browser-background` fills under `text-primary`: near-white text on white                                | Browser                                     |
| `src/lib/components/UserMenu.svelte`                                                                    | Opens a `dialog`, transparent until Modal is restyled                                                              | PR 2                                        |
| Viewer side panels (`TaskPanel.svelte` etc.)                                                            | Carbon's 63 px right button padding may overflow narrow panels                                                     | Viewer                                      |
| Unconverted shadcn `ui/` components                                                                     | `bg-popover`/`bg-background` gone: menus, popovers and dialogs are transparent                                     | The layer that first restyles each          |

Viewer decisions already taken: the image area is `#000000`, and image drawings (segmentations,
points, grids) keep their own colours outside the theme.
