# Input Validation

Rigorous input validation is a core pillar of the OsuRender API security model.

## Replay Validation (`.osr`)

When a user uploads a replay file, it undergoes the following checks:

1. **Extension**: Must end in `.osr`
2. **Size**: Must not exceed `MAX_REPLAY_SIZE_MB` (default 50 MB)
3. **Empty Check**: File size must be > 0
4. **Structural Integrity**: The file is parsed using the `osrparse` library. If parsing fails, the file is rejected.
5. **Game Mode**: Only osu!standard replays (`mode == 0`) are supported. Taiko, Catch, and Mania replays are rejected.

## Skin Validation (`.osk`)

Skin uploads are particularly dangerous because they are ZIP archives that will be extracted on the worker nodes. They undergo extreme scrutiny:

1. **Extension**: Must end in `.osk`
2. **Size**: Must not exceed `MAX_SKIN_SIZE_MB` (default 200 MB)
3. **Magic Bytes**: Must start with `PK` (the standard ZIP header)
4. **ZIP Structure**: The archive must pass Python's `zipfile.testzip()`
5. **Entry Count**: Maximum of 10,000 files/directories inside the archive
6. **Compression Ratio**: To prevent zip bombs, the ratio of uncompressed size to compressed size must not exceed 100x.
7. **Nesting Depth**: Directory depth cannot exceed 3 levels.
8. **Nested Archives**: No `.zip` or `.osk` files are allowed *inside* the skin archive.

### Extraction Safety

Even after validation, the worker node extracts the skin carefully:
- It uses `zipfile.ZipFile.extractall()` but overrides it with a custom secure extractor.
- Path traversal (`../`) is stripped.
- Absolute paths (`/etc/passwd`) are stripped.
- The total extracted size is tracked byte-by-byte and aborted if it exceeds a hard limit.

## API Parameter Validation

All API endpoints use Pydantic for request validation:

- **Skin Name**: Must match the regex `^[a-zA-Z0-9_ -]+$`
- **Resolution**: Must be exactly `"1080p"` or `"4k"`
- **Background Dim**: Must be a float. If > 1.0, it is automatically normalized (e.g., `95` becomes `0.95`). If < 0.0 or > 100.0, it is rejected.
- **Booleans**: Fields like `motion_blur` must be valid booleans.
