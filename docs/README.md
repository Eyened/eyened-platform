# EyeNED Platform Documentation

This directory contains the public documentation site for EyeNED Platform. It is built with Astro Starlight and published under `https://eyened.github.io/eyened-platform/`.

## Structure

- `src/content/docs/` contains the documentation pages.
- `src/assets/` contains images referenced by MDX pages.
- `astro.config.mjs` configures the site URL, base path, and sidebar.

## Local Development

Run commands from this directory:

```bash
npm install
npm run dev
```

The dev server runs on `localhost:4321` by default.

## Build And Preview

```bash
npm run build
npm run preview
```

Run `npm run build` before publishing release documentation. This catches broken MDX, links that Astro can validate, and sidebar configuration errors.

## Release Documentation Checklist

- Update `src/content/docs/release_notes.mdx` with concise user-facing changes.
- Check setup docs when Docker, database, worker, authentication, storage, or import behavior changes.
- Check ORM docs when `eorm` commands, importer behavior, configuration, or database entities change.
- Check API docs when routes, request bodies, response shapes, or authentication behavior change.
