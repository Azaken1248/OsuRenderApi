---
title: "Skins API"
description: "List, upload, and manage osu! skins for replay rendering. Supported formats, upload limits, and skin selection for render jobs."
---

# Skins API

## GET /v1/skins — List Available Skins

<span class="custom-badge badge-get">GET</span> `/v1/skins`

Returns a list of all available osu! skins stored in object storage.

### Example

```bash
curl http://localhost:8727/v1/skins
```

### Response (200 OK)

```json
{
  "skins": [
    "Default",
    "WhiteCat 1.0",
    "Rafis HDDT",
    "mrekk skin v3"
  ]
}
```

---

## POST /v1/skins/upload — Upload a Custom Skin

<span class="custom-badge badge-post">POST</span> `/v1/skins/upload`

Upload a `.osk` skin file to make it available for rendering jobs.

**Rate Limit:** 2 requests per minute per IP

### Request

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skin` | `File` | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> | The `.osk` skin file (ZIP archive) |

### Example

```bash
curl -X POST http://localhost:8727/v1/skins/upload \
  -F "skin=@WhiteCat 1.0.osk"
```

### Response (200 OK)

```json
{
  "success": true,
  "skin_name": "WhiteCat 1.0",
  "message": "Skin 'WhiteCat 1.0' uploaded successfully."
}
```

### Validation Rules

The skin upload undergoes extensive security validation:

| Check | Limit | Error |
|-------|-------|-------|
| File extension | Must be `.osk` | 400 |
| File size | ≤ `MAX_SKIN_SIZE_MB` (200 MB) | 413 |
| Magic bytes | Must start with `PK` (ZIP header) | 415 |
| ZIP entry count | ≤ 10,000 entries | 422 |
| Compression ratio | ≤ 100x (zip bomb protection) | 422 |
| Nesting depth | ≤ 3 levels | 422 |
| Nested archives | No `.zip` or `.osk` inside | 422 |
| Corruption | `testzip()` must pass | 422 |
| Filename | Alphanumeric, spaces, hyphens, underscores only | 422 |

::: warning Zip Bomb Protection
The system validates both compression ratio and total uncompressed size to prevent decompression bomb attacks that could exhaust disk or memory resources.
:::
