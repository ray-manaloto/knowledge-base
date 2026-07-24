---
title: Configuration Reference
---

# Configuration Reference

## `checkOrigin`

**Type:** `boolean`
**Default:** `true`
**Added in:** `astro@4.9.0`

When enabled, Astro checks that the `Origin` header matches the request URL.

```ts
export default defineConfig({
  security: {
    checkOrigin: false,
  },
})
```

## `trailingSlash`

**Type:** `'always' | 'never' | 'ignore'`
**Default:** `'ignore'`

Controls route matching for trailing slashes.

## `build.inlineStylesheets`

**Type:** `'always' | 'auto' | 'never'`
**Default:** `'auto'`

| Option | Behaviour |
| --- | --- |
| `always` | Inline every stylesheet |
| `auto` | Inline below `ASSET_LIMIT` |
| `never` | Never inline |

## `server.port`

**Type:** `number`
**Default:** `4321`

Set with `astro dev --port 8080` or `PORT=8080`.

## `experimental.contentIntellisense`

**Type:** `boolean`
**Default:** `false`

Enables `.astro/collections` type generation via `getCollection()`.
