# utils

Pure helper functions and constants. No FastAPI or database dependencies from here (except where they import app.core for config).

## Modules

- **constants.py** — Application constants; may reference app.models enums.
- **date_time_styling.py** — Date/datetime formatting and display helpers.
- **embedding.py** — Embeddings client (cached singleton) for vector generation.
- **formatters.py** — Response formatting utilities.
- **validators.py** — Input validation and normalization.
