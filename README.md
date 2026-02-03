# Pantry Server

FastAPI backend for the Pantry application. Provides REST API endpoints for managing pantry items, recipes, shopping lists, and households with Supabase integration and AI-powered features using Google Gemini.

## Table of Contents

- [Overview](#overview)
- [Current Status](#current-status)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the Server](#running-the-server)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [Development Guidelines](#development-guidelines)

## Overview

Pantry Server is a modern, scalable backend API built with FastAPI that enables users to:

- **Manage Pantry Items**: Track food inventory with categories, quantities, units, and expiry dates
- **Recipe Management**: Create, search, and generate recipes using AI
- **Shopping Lists**: Generate and manage shopping lists based on pantry needs
- **Household Collaboration**: Share pantries and shopping lists with household members
- **User Preferences**: Configure alerts and reminders for pantry management

## Current Status

### ✅ Implemented

#### Core Infrastructure

- ✅ FastAPI application with lifespan management
- ✅ Configuration management with Pydantic Settings
- ✅ Structured logging system
- ✅ Global exception handling
- ✅ Health check endpoint (`GET /health`)

#### Authentication & Security

- ✅ Supabase authentication integration
- ✅ Bearer token validation
- ✅ User authentication dependency (`get_current_user`)
- ✅ Row Level Security (RLS) support via anon key client

#### Data Models

- ✅ **Pantry Models**: Complete schema for pantry items with categories, units, expiry tracking
- ✅ **Recipe Models**: Full recipe structure with ingredients, instructions, dietary tags
- ✅ **Shopping List Models**: Shopping list items with purchase tracking
- ✅ **Household Models**: Household management and member models
- ✅ **User Models**: User preferences for alerts and reminders

#### Services

- ✅ Supabase client service (anon and service role)
- ✅ Gemini AI client with LRU caching
- ✅ Embeddings client for vector operations

#### Utilities

- ✅ Authentication utilities
- ✅ Input validators and normalizers
- ✅ Response formatters
- ✅ Application constants

### 🚧 In Progress / Planned

- ⏳ **API Routes**: Endpoints for CRUD operations (models defined, routes pending)
- ⏳ **Recipe Generation**: AI-powered recipe generation from pantry items
- ⏳ **Shopping List Generation**: Automatic list creation based on pantry state
- ⏳ **Background Workers**: Embedding generation and batch processing
- ⏳ **Rate Limiting**: API rate limiting middleware
- ⏳ **CORS Configuration**: Cross-origin resource sharing setup

## Tech Stack

### Core Framework

- **FastAPI** - Modern, fast web framework for building APIs
- **Uvicorn** - ASGI server for production deployment
- **Pydantic** - Data validation using Python type annotations
- **pydantic-settings** - Settings management from environment variables

### Database & Authentication

- **Supabase** - PostgreSQL database with built-in authentication
- **python-jose** - JWT token handling
- **passlib** - Password hashing utilities

### AI & Machine Learning

- **LangChain** - Framework for building LLM applications
- **LangGraph** - State management for complex AI workflows
- **langchain-google-genai** - Google Gemini integration
- **Google Generative AI** - Gemini models for text and embeddings

### Utilities

- **httpx** - Async HTTP client
- **slowapi** - Rate limiting middleware
- **psutil** - System monitoring
- **python-multipart** - Form data handling
- **python-dateutil** - Date parsing utilities

## Prerequisites

- **Python 3.11+** (tested with Python 3.11+)
- **Supabase Account** - For database and authentication
- **Google Cloud Account** - For Gemini API access (optional, for AI features)
- **`.env` file** - Environment variables (see [Environment Variables](#environment-variables))

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pantry/server
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example (if available)
cp .env.example .env

# Or create manually
touch .env
```

See [Environment Variables](#environment-variables) for required configuration.

### 5. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.11+

# Verify FastAPI installation
python -c "import fastapi; print(fastapi.__version__)"
```

## Running the Server

### Development Mode

Runs with auto-reload on file changes:

```bash
uvicorn app.main:app --reload
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Using FastAPI CLI

```bash
fastapi dev app/main.py
```

### Access Points

- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive API Docs (Swagger)**: `http://127.0.0.1:8000/docs`
- **Alternative API Docs (ReDoc)**: `http://127.0.0.1:8000/redoc`
- **OpenAPI JSON**: `http://127.0.0.1:8000/openapi.json`

## Project Structure

```
app/
├── __init__.py
├── main.py                    # FastAPI app factory, lifespan, middleware
│
├── core/                      # Core application configuration
│   ├── __init__.py
│   ├── config.py             # AppSettings, environment configuration
│   ├── exceptions.py         # Exception handlers and custom errors
│   └── logging.py            # Logging configuration
│
├── models/                    # Pydantic schemas and domain models
│   ├── __init__.py
│   ├── household.py          # Household and member models
│   ├── pantry.py             # Pantry item models and enums
│   ├── recipe.py             # Recipe models and AI request/response
│   ├── shopping_list.py      # Shopping list models
│   └── user.py               # User preferences models
│
├── routers/                   # API route definitions
│   ├── __init__.py
│   └── health_routes.py      # Health check endpoint
│
├── services/                  # Business logic and external integrations
│   ├── __init__.py
│   ├── gemini.py             # Gemini AI client (cached singleton)
│   └── supabase.py           # Supabase client dependencies
│
└── utils/                     # Utility functions and helpers
    ├── __init__.py
    ├── auth.py               # Authentication dependencies
    ├── constants.py          # Application constants
    ├── embedding.py          # Embeddings client (cached singleton)
    ├── formatters.py         # Response formatting utilities
    └── validators.py         # Input validation helpers
```

## Architecture

### Design Principles

- **Functional Programming**: Prefer pure functions over classes where possible
- **Dependency Injection**: Use FastAPI's dependency system for shared resources
- **Separation of Concerns**: Clear boundaries between routes, services, and utilities
- **Type Safety**: Comprehensive type hints throughout the codebase
- **Error Handling**: Early returns, guard clauses, and consistent error responses

### Key Patterns

#### Singleton Services

Client instances (Gemini, Embeddings, Supabase) use `@lru_cache` for singleton behavior:

```python
@lru_cache(maxsize=1)
def get_gemini_client() -> ChatGoogleGenerativeAI:
    """Cached singleton client instance"""
    return ChatGoogleGenerativeAI(...)
```

#### Model Hierarchy

Pydantic models follow a consistent pattern:

- `*Base` - Base model with common fields
- `*Create` - For creation requests
- `*Update` - For partial updates (all fields optional)
- `*Response` - For API responses

#### Dependency Injection

FastAPI dependencies for:

- Authentication: `get_current_user()`
- Database clients: `get_supabase_client()`, `get_supabase_service_role_client()`
- AI clients: `get_gemini_client()`, `embeddings_client()`

## Environment Variables

### Required Variables

| Variable                    | Description                                      | Example                                   |
| --------------------------- | ------------------------------------------------ | ----------------------------------------- |
| `SUPABASE_URL`              | Supabase project URL                             | `https://xxxxx.supabase.co`               |
| `SUPABASE_ANON_KEY`         | Supabase anonymous/public key                    | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (for admin operations) | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |

### Optional Variables

#### Application Configuration

| Variable    | Description         | Default         |
| ----------- | ------------------- | --------------- |
| `APP_ENV`   | Runtime environment | `development`   |
| `APP_NAME`  | Application name    | `pantry-server` |
| `PORT`      | Server port         | `8000`          |
| `HOST`      | Server host         | `0.0.0.0`       |
| `RELOAD`    | Enable auto-reload  | `True`          |
| `DEBUG`     | Debug mode          | `False`         |
| `LOG_LEVEL` | Logging level       | `INFO`          |

#### CORS Configuration

| Variable       | Description                                           | Default                                                   |
| -------------- | ----------------------------------------------------- | --------------------------------------------------------- |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated or Python list) | `['http://localhost:3000', 'http://localhost:5173', '*']` |

#### Gemini AI Configuration

| Variable                                  | Description                 | Default                |
| ----------------------------------------- | --------------------------- | ---------------------- |
| `GOOGLE_GENERATIVE_AI_API_KEY`            | Google AI API key           | —                      |
| `GEMINI_MODEL`                            | Gemini model name           | `gemini-2.5-flash`     |
| `GEMINI_TEMPERATURE`                      | Model temperature (0.0-1.0) | `0.0`                  |
| `GEMINI_MAX_TOKENS`                       | Maximum tokens per response | `1000`                 |
| `GEMINI_MAX_RETRIES`                      | Maximum retry attempts      | `2`                    |
| `GEMINI_EMBEDDINGS_MODEL`                 | Embeddings model name       | `gemini-embedding-001` |
| `GEMINI_EMBEDDINGS_OUTPUT_DIMENSIONALITY` | Embedding vector size       | `768`                  |

#### Rate Limiting

| Variable                | Description          | Default |
| ----------------------- | -------------------- | ------- |
| `RATE_LIMIT_ENABLED`    | Enable rate limiting | `True`  |
| `RATE_LIMIT_PER_MINUTE` | Requests per minute  | `60`    |

#### Background Workers

| Variable                    | Description                     | Default |
| --------------------------- | ------------------------------- | ------- |
| `ENABLE_BACKGROUND_WORKERS` | Enable background processing    | `True`  |
| `EMBEDDING_BATCH_SIZE`      | Batch size for embeddings       | `50`    |
| `EMBEDDING_WORKER_INTERVAL` | Worker check interval (seconds) | `5`     |

## API Documentation

### Current Endpoints

#### Health Check

- **GET** `/health` - Returns application health status
  - Response: `{"status": "ok"}`

#### Root

- **GET** `/` - Simple status endpoint (excluded from OpenAPI)
  - Response: `{"status": "ok"}`

### Planned Endpoints

Routes are defined in models but not yet implemented. Planned endpoints include:

#### Pantry Management

- `GET /api/pantry` - List pantry items
- `POST /api/pantry` - Add pantry item
- `GET /api/pantry/{item_id}` - Get pantry item
- `PUT /api/pantry/{item_id}` - Update pantry item
- `DELETE /api/pantry/{item_id}` - Delete pantry item
- `GET /api/pantry/summary` - Get pantry summary

#### Recipe Management

- `GET /api/recipes` - List recipes
- `POST /api/recipes` - Create recipe
- `GET /api/recipes/{recipe_id}` - Get recipe
- `POST /api/recipes/generate` - Generate recipe from pantry
- `POST /api/recipes/search` - Search recipes
- `POST /api/recipes/{recipe_id}/use-ingredients` - Mark ingredients as used

#### Shopping Lists

- `GET /api/shopping-lists` - List shopping lists
- `POST /api/shopping-lists` - Create shopping list
- `GET /api/shopping-lists/{list_id}` - Get shopping list
- `POST /api/shopping-lists/generate` - Generate from pantry
- `POST /api/shopping-lists/{list_id}/mark-purchased` - Mark items purchased

#### Households

- `GET /api/households` - List user's households
- `POST /api/households` - Create household
- `GET /api/households/{household_id}` - Get household
- `POST /api/households/join` - Join household
- `POST /api/households/{household_id}/leave` - Leave household

#### User Preferences

- `GET /api/user/preferences` - Get user preferences
- `PUT /api/user/preferences` - Update user preferences

## Development Guidelines

### Code Style

- **Type Hints**: All functions must have type hints
- **Docstrings**: Use Google-style docstrings for public functions
- **Naming**: Use descriptive names with auxiliary verbs (`is_active`, `has_permission`)
- **Early Returns**: Handle errors and edge cases at the beginning of functions
- **Guard Clauses**: Use guard clauses for preconditions

### Adding New Routes

1. Create route file in `app/routers/`
2. Define router with `APIRouter(tags=["tag-name"])`
3. Add routes with proper type hints and response models
4. Include router in `app/main.py`:

```python
from app.routers import your_router

app.include_router(your_router, prefix="/api/your-prefix")
```

### Adding New Models

1. Create model file in `app/models/` or add to existing file
2. Follow the pattern: `*Base`, `*Create`, `*Update`, `*Response`
3. Use Pydantic `Field` for validation and descriptions
4. Export models in `__all__`

### Adding New Services

1. Create service file in `app/services/`
2. Use `@lru_cache(maxsize=1)` for singleton clients
3. Keep I/O and external API calls in services
4. Use dependency injection for shared resources

### Testing

```bash
# Run tests (when implemented)
pytest

# Run with coverage
pytest --cov=app
```

### Code Quality

```bash
# Format code
black app/

# Lint code
ruff check app/

# Type checking
mypy app/
```

## Contributing

1. Create a feature branch
2. Make your changes following the development guidelines
3. Ensure all tests pass
4. Update documentation as needed
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions, please open an issue in the repository.
