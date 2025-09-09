# Learn Kuch Bhi

A comprehensive learning platform that generates educational content including animated videos and flashcards using AI. The platform combines Manim for mathematical animations and intelligent content generation to create personalized learning experiences.

## Features

- **AI-Powered Video Generation**: Create educational Manim animations from text prompts
- **Smart Flashcard Creation**: Generate comprehensive flashcard sets with intelligent topic organization
- **Multi-Agent System**: Advanced outline-based flashcard generation with concurrent processing
- **User Management**: Complete authentication and user session handling
- **Database Integration**: Full persistence for all generated content with status tracking
- **File Management**: Organized video storage and serving with automatic cleanup

## Architecture

### Core Components

- **Video Generator**: AI-driven Manim video creation pipeline
- **Flashcards**: Outline-based multi-topic flashcard generation
- **Database Layer**: PostgreSQL with SQLAlchemy ORM and Alembic migrations
- **Authentication**: FastAPI-Users integration
- **File Management**: Organized storage system for generated content

### Database Schema

#### Video Generation Tables
- `video_generation_requests`: Tracks generation requests with parameters
- `video_generation_results`: Stores pipeline results and metadata
- `videos`: Final video records with serving information
- `video_codes`: Generated Manim code storage

#### Flashcard Tables
- `multi_flashcards_results`: Multi-agent generation runs (stores outline JSON, status, timings)
- `fc_topics`: Topics under a run (`multi_result_id` FK)
- `fc_subtopics`: Subtopics under a topic (`topic_id` FK)
- `flashcard_sets`: Flashcard set for a subtopic (`subtopic_id` FK, also `multi_result_id` for convenience)
- `flashcards`: Individual question-answer pairs (`flashcard_set_id` FK)

## Quick Start

### Prerequisites

- Python 3.13+
- PostgreSQL database
- uv package manager
- Redis (for caching and sessions)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd learn-kuch-bhi
```

2. Install dependencies:
```bash
uv sync
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
```env
# Database
POSTGRES_HOST=localhost
POSTGRES_DB_PORT=5432
POSTGRES_DB_NAME=learn_kuch_bhi
POSTGRES_DB_USER=your_user
POSTGRES_DB_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

# Application
APP_NAME=learn-kuch-bhi
APP_PORT=9000
MODE=dev
JWT_SECRET=your_secret_key

# AI APIs
GEMINI_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key

# Optional: Context7 MCP
CONTEXT7_ENABLED=true
CONTEXT7_API_KEY=your_context7_key
```

4. Run database migrations:
```bash
uv run alembic upgrade head
```

5. Start the application:
```bash
uv run python main.py
```

## Usage

### Video Generation

#### Basic Usage
```python
from app.modules.video_generator.main import VideoGenerator

# Simple generation
generator = VideoGenerator()
result = await generator.generate("Explain the Pythagorean theorem with animation")

# Synchronous version
result = generator.generate_sync("Animate a sine wave")
```

#### Database Integration
```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.video_generator.main import VideoGenerator

generator = VideoGenerator()
result, video_id = await generator.generate_with_db(
    session=session,
    user_id=1,
    prompt="Create an animation explaining calculus derivatives",
    title="Calculus Derivatives",
    description="Educational animation about derivatives"
)
```

### Flashcard Generation (Outline-based)
```python
from app.modules.flashcards.main import MultiFlashcardsGenerator

generator = MultiFlashcardsGenerator(concurrency=6)

# Generate comprehensive flashcards with topic/subtopic outline (in-memory)
result = await generator.generate("Advanced Physics - Quantum Mechanics")

# Database integration: persists the run, topics/subtopics, and all subtopic sets
db_result = await generator.generate_with_db(
    session=session,
    user_id=1,
    base_prompt="Computer Science - Data Structures and Algorithms"
)

# db_result is a MultiFlashcardsResult row; related data accessible via ORM relationships
print(db_result.id, len(db_result.topics))
```

### CLI Usage

#### Video Generation
```bash
# Generate a video
uv run python -m app.modules.video_generator.main "Explain Newton's laws"

# Generate with custom parameters
uv run python -m app.modules.video_generator.cli \
    --prompt "Animate Fourier transforms" \
    --scene-name "FourierScene" \
    --max-lint-rounds 3
```

#### Flashcard Generation
```bash
# Generate multi-topic flashcards (outline + per-subtopic sets)
uv run flashcards-gen generate-multi --prompt "Organic Chemistry basics"

# or via module
uv run python -m app.modules.flashcards.cli generate-multi --prompt "Organic Chemistry basics"
```

## API Integration

### Video Generation Endpoint Example
```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.video_generator.main import VideoGenerator
from app.core.db import get_session

app = FastAPI()

@app.post("/generate-video")
async def generate_video(
    request: VideoGenerationRequest,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):
    generator = VideoGenerator()
    result, video_id = await generator.generate_with_db(
        session=session,
        user_id=current_user.id,
        prompt=request.prompt,
        title=request.title,
        description=request.description
    )
    
    return {
        "success": result.ok,
        "video_id": video_id,
        "video_path": result.video_path,
        "message": "Video generated successfully" if result.ok else "Generation failed"
    }
```

### Flashcard Generation Endpoint Example (Outline-based only)
```python
@app.post("/generate-flashcards")
async def generate_flashcards(
    request: FlashcardRequest,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):
    generator = MultiFlashcardsGenerator()
    db_result = await generator.generate_with_db(
        session=session,
        user_id=current_user.id,
        base_prompt=request.prompt
    )

    return {
        "run_id": db_result.id,
        "topics": len(db_result.topics),
        "subtopics": sum(len(t.subtopics) for t in db_result.topics),
        "status": str(db_result.status.value),
    }
```

## Configuration

### Video Generation Parameters
- `scene_file`: Python file name for the scene (default: "scene.py")
- `scene_name`: Class name for the Manim scene (default: "GeneratedScene")
- `extra_packages`: Additional Python packages to install
- `max_lint_batch_rounds`: Maximum linting iterations (default: 2)
- `max_post_runtime_lint_rounds`: Post-execution linting rounds (default: 2)
- `max_runtime_fix_attempts`: Maximum runtime error fixes (default: 2)

### Flashcard Generation Parameters
- `concurrency`: Number of concurrent subtopic generations (default: 6)
- Multi-agent processing for comprehensive topic coverage

### File Management
Videos are automatically organized in the following structure:
```text
videos/
├── serving/
│   └── user_{user_id}/
│       └── {timestamp}_{sanitized_title}.mp4
└── temp/
    └── (temporary files, auto-cleaned)
```

## Database Management

### Migrations
```bash
# Create a new migration
uv run alembic revision --autogenerate -m "Description of changes"

# Apply migrations
uv run alembic upgrade head

# Check current migration status
uv run alembic current

# Check if migrations are needed
uv run alembic check
```

### Database Schema Updates
The system includes comprehensive schema management for:
- Video generation request tracking
- Flashcard relationship management
- User content association
- Status monitoring for all operations

## Development

### Project Structure

```text
app/
├── core/
│   ├── config.py            # Application configuration settings
│   ├── db_services.py       # Database service and utility functions
│   ├── video_manager.py     # Video file storage and management
│   └── db/
│       ├── base.py          # SQLAlchemy base class
│       ├── schemas/         # ORM models and schema definitions
│       └── migrations/      # Alembic migration scripts
├── modules/
│   ├── auth/                # User authentication and session management
│   ├── video_generator/     # Manim-based video generation logic
│   └── flashcards/          # Flashcard and outline generation logic
└── apis/                    # FastAPI route handlers and endpoints
```

### Adding New Features

1. **Database Changes**: Create migrations for schema updates
2. **Service Layer**: Add methods to `db_services.py` for data operations
3. **Generator Updates**: Extend generator classes with new functionality
4. **API Integration**: Create endpoints that use the service layer

### Testing

```bash
# Run tests (when test suite is available)
uv run pytest

# Check code quality
uv run ruff check
uv run mypy app/
```

## Error Handling

The system includes comprehensive error handling:
- **Generation Failures**: Tracked in database with error messages
- **File Operations**: Graceful handling of file system errors
- **Database Operations**: Transaction management and rollback support
- **Status Tracking**: Real-time status updates for long-running operations

## Monitoring

### Status Tracking
All generation operations include status tracking:
- `PENDING`: Request created, not started
- `PROCESSING`: Generation in progress
- `COMPLETED`: Successfully completed
- `FAILED`: Generation failed with error details

### Logging
Comprehensive logging throughout the pipeline:
- Generation request details
- Processing steps and timing
- Error messages and stack traces
- File operation results

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with appropriate tests
4. Update documentation
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions:
- Create an issue in the repository
- Check the documentation
- Review error logs for debugging information

---

**Note**: This platform is designed for educational content generation. Ensure you have appropriate API keys and computing resources for AI model usage and video rendering.
