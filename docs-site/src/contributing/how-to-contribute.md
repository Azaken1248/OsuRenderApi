# How to Contribute

We welcome contributions to OsuRender API! Whether it's a bug fix, new feature, or documentation improvement, your help is appreciated.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
   ```bash
   git clone https://github.com/YOUR_USERNAME/OsuRenderApi.git
   cd OsuRenderApi
   ```
3. **Set up the local environment** following the [Local Development Setup](/src/development/local-setup) guide
4. **Create a new branch** for your feature or bugfix
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```

## Finding Things to Work On

- Check the [Issues](https://github.com/Azaken1248/OsuRenderApi/issues) page
- Look for issues labeled `good first issue` or `help wanted`
- Review the [Roadmap](/src/roadmap/roadmap) for upcoming features

If you plan to work on a major new feature, please open an issue first to discuss the design before writing code.

## Development Workflow

1. Write your code
2. Write tests covering your changes
3. Ensure all tests pass: `MOCK_DANSER=1 pytest`
4. Format your code: `black src/ tests/ scripts/`
5. Lint your code: `ruff check src/`
6. Check types: `pyright src/`

## Making Changes to the Database

If your feature requires a database schema change:

1. Update the SQLAlchemy models in `src/db/models.py`
2. Generate an Alembic migration:
   ```bash
   alembic revision --autogenerate -m "Add new column to jobs"
   ```
3. Review the generated script in `alembic/versions/`
4. Apply the migration locally: `alembic upgrade head`
5. Commit the migration script along with your code changes
