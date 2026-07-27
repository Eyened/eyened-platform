# Form PointTool ↔ PointField sync

**Date:** 2026-07-27  
**Status:** Accepted (approach 1) / implemented

## Problem

Form-armed `PointTool` remounted or fought with PointField because live edits wrote into form `value`, and MainViewer’s `$effect` re-read that value. Dragging janked; chips/labels lagged. ETDRS/Registration already keep a live list on the tool.

## Design

While a form point field is armed, `FormPointSession.fieldValue` is the source of truth:

| Writer | Action |
|--------|--------|
| PointTool `onChange` | `session.setPoints(publicId, points)` |
| PointTool `onPersist` | setPoints + `session.persist()` → form `onchange` |
| PointField chips | read `session.fieldValue` when armed; writes go to session then persist |
| disarm / arm-replace | `persist()` then clear session |

MainViewer mounts the tool when `session.key` changes only; a nested sync copies `session.getPoints(publicId)` → `tool.points` so PointField edits and other viewers stay aligned without remounting on every drag move.

Form `value` / server remain the durable store; the session is the ephemeral live mirror.
