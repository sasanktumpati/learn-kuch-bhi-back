# API Reference

All routes are prefixed with `/{API_VERSION}`. Default is `/v1` (see `APP_VERSION`).

Authentication: use Bearer JWT in header `Authorization: Bearer <token>`.

Sorting: list endpoints return results ordered by creation time descending (newest first).

---

## Flashcards

### POST `/v1/flashcards/outline`
- Purpose: Generate an outline (topics + subtopics) for a subject.
- Request
```
{
  "base_prompt": "Linear Algebra"
}
```
- Response
```
{
  "outline": {
    "title": "string",
    "topics": [
      {
        "name": "string",
        "subtopics": [
          {"name": "string", "description": "string|null"}
        ]
      }
    ]
  }
}
```

### POST `/v1/flashcards/generate`
- Purpose: Queue a multi-topic flashcards generation run (async). Concurrency is fixed at 4 internally.
- Request
```
{
  "base_prompt": "Linear Algebra"
}
```
- Response
```
{
  "run": {
    "id": 123,
    "status": "pending|processing|completed|failed",
    "outline": {},
    "created_at": "2025-01-01T12:00:00Z",
    "completed_at": null,
    "sets_created": 0
  },
  "status_url": "/v1/flashcards/runs/123",
  "sets_url": "/v1/flashcards/runs/123/sets"
}
```
Notes:
- Poll `status_url` for the run status.
- Poll `sets_url` to fetch sets as they are created and finalized.

### GET `/v1/flashcards/runs`
- Purpose: List flashcards runs for current user.
- Response
```
[
  {
    "id": 123,
    "status": "processing",
    "outline": {},
    "created_at": "2025-01-01T12:00:00Z",
    "completed_at": null,
    "sets_created": 4
  }
]
```

### GET `/v1/flashcards/runs/{run_id}`
- Purpose: Get a single run status.
- Response: `MultiRunSummary` as above.

### GET `/v1/flashcards/runs/{run_id}/sets`
- Purpose: List sets produced by a run (updates as generation proceeds).
- Response
```
[
  {
    "id": 345,
    "title": "Topic — Subtopic",
    "description": "Generating... or final description",
    "tags": ["tag1", "tag2"],
    "status": "processing|completed",
    "created_at": "2025-01-01T12:05:00Z"
  }
]
```

### GET `/v1/flashcards/sets`
- Purpose: List all flashcard sets for current user.
- Response: array of `FlashcardSetSummary` (same schema as run sets above).

### GET `/v1/flashcards/sets/{set_id}`
- Purpose: Get a flashcard set with cards.
- Response
```
{
  "id": 345,
  "title": "string",
  "description": "string",
  "tags": ["tag"],
  "status": "completed|processing",
  "created_at": "2025-01-01T12:05:00Z",
  "flashcards": [
    {"id": 1, "question": "Q?", "answer": "A.", "order_index": 0}
  ]
}
```

---

## Videos

### POST `/v1/videos/generate`
- Purpose: Queue a video generation pipeline run (async).
- Request
```
{
  "prompt": "Animate Pythagoras",
  "title": "Pythagoras",
  "description": "Optional description",
  "scene_file": "scene.py",
  "scene_name": "GeneratedScene",
  "extra_packages": ["numpy"],
  "max_lint_batch_rounds": 2,
  "max_post_runtime_lint_rounds": 2,
  "max_runtime_fix_attempts": 2
}
```
- Response
```
{
  "request_id": 456,
  "video_uuid": "4f3e2d...",
  "video_id": null,
  "status": "pending",
  "status_url": "/v1/videos/requests/4f3e2d...",
  "pipeline": {
    "ok": false,
    "video_path": null,
    "lint_issues": [],
    "runtime_errors": []
  }
}
```
Notes:
- Poll `status_url` to track progress. When completed and successful, a `Videos` record is created and available via list/get endpoints.

### GET `/v1/videos/requests`
- Purpose: List your generation requests (to discover `video_uuid`).
- Response
```
[
  {
    "id": 456,
    "video_uuid": "4f3e2d...",
    "status": "processing|completed|failed|pending",
    "created_at": "2025-01-01T12:00:00Z",
    "started_at": "2025-01-01T12:01:00Z",
    "completed_at": null
  }
]
```

### GET `/v1/videos/requests/{video_uuid}`
- Purpose: Poll request status/result by UUID.
- Response
```
{
  "request_id": 456,
  "video_uuid": "4f3e2d...",
  "status": "completed|failed|processing|pending",
  "started_at": "2025-01-01T12:01:00Z",
  "completed_at": "2025-01-01T12:08:00Z",
  "result_id": 789,
  "video_id": 101,
  "error_message": null
}
```

### GET `/v1/videos`
- Purpose: List your videos (newest first).
- Response
```
[
  {
    "id": 101,
    "title": "Pythagoras",
    "description": "...",
    "path": "/media/user/101.mp4",
    "original_path": "/tmp/session/.../media/videos.mp4",
    "file_size": 1234567,
    "duration": 42.0,
    "uploaded_at": "2025-01-01T12:09:00Z"
  }
]
```

### GET `/v1/videos/{video_id}`
- Purpose: Get one video’s metadata.
- Response: single object with same fields as list items.

---

## Errors
- 401 Unauthorized: missing/invalid token.
- 404 Not Found: resource does not exist or not owned by caller.
- 422 Unprocessable Entity: invalid input payload.

---

## Notes
- Background tasks run in-process; for multi-instance deployments use a real queue/broker.
- Flashcards sets appear incrementally; poll the run’s `sets_url` for latest.
- Sorting for lists is by latest creation time first.
