# Server-Sent Events (SSE) Reference

This document describes the real-time endpoints for streaming status updates via SSE.

General:
- Media type: `text/event-stream`
- Each event is formatted as lines of `event: <name>` and `data: <json>`, separated by a blank line.
- Connections close automatically after a terminal `end` event.

---

## Flashcards SSE

Endpoint: `GET /v1/flashcards/runs/{run_id}/events`

Purpose: Stream a flashcards run’s status transitions and newly created sets as they appear.

Events
- `event: status`
  - Emitted whenever the run’s status changes.
  - Data
  ```json
  {
    "status": "pending|processing|completed|failed",
    "sets_created": 4,
    "sets_completed": 2,
    "total_expected": 12,
    "progress_percent": 16.67
  }
  ```
  - Notes
    - `total_expected` is derived from the run’s outline (sum of subtopics). It may be null if the outline is not yet generated.
    - `sets_created` counts all sets created for the run (includes processing and completed).
    - `sets_completed` counts only sets with status `completed`.
    - `progress_percent` is derived as `(sets_completed / total_expected) * 100` when `total_expected > 0`.

- `event: set`
  - Emitted for each newly observed flashcard set.
  - Data
  ```json
  {
    "id": 345,
    "title": "Topic — Subtopic",
    "description": "Generating... or final description",
    "tags": ["tag1", "tag2"],
    "status": "processing|completed",
    "created_at": "2025-01-01T12:05:00Z"
  }
  ```

- `event: end`
  - Emitted once when the run reaches a terminal state.
  - Data
  ```json
  { "status": "completed|failed" }
  ```

- `event: ping`
  - Emitted periodically (every ~15s) to keep connections alive.
  - Data: `{ "ts": "ISO-8601 timestamp" }`

---

## Videos SSE

Endpoint: `GET /v1/videos/requests/{video_uuid}/events`

Purpose: Stream a video generation request’s status transitions.

Events
- `event: status`
  - Emitted whenever the request status changes.
  - Data
  ```json
  {
    "status": "pending|processing|completed|failed",
    "request_id": 456,
    "video_uuid": "4f3e2d...",
    "started_at": "2025-01-01T12:01:00Z",
    "completed_at": null
  }
  ```

- `event: end`
  - Emitted once when the request reaches a terminal state.
  - Data
  ```json
  { "status": "completed|failed" }
  ```

---

Notes
- These SSE endpoints poll the database every 1s and push changes only when detected.
- For browser clients, ensure your frontend uses EventSource and that CORS allows `text/event-stream` if served across origins.
 - `event: ping`
   - Emitted periodically (every ~15s) to keep connections alive.
   - Data: `{ "ts": "ISO-8601 timestamp" }`
