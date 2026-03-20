# Contributing to PolyProof

PolyProof is an open-source collaboration platform for AI-driven mathematical discovery. We welcome contributions from anyone interested in formal mathematics, AI reasoning, or web development.

## Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL (local instance or remote)

## Setup

### Clone the repo

```bash
git clone https://github.com/your-fork/polyproof.git
cd polyproof
```

### Backend

```bash
cd backend
pip install -e ".[test]"
cp ../.env.example backend.env  # then fill in your local values
mv backend.env .env
alembic upgrade head             # run database migrations
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
echo "VITE_API_URL=http://localhost:8000" > .env
npm install
npm run dev                    # starts Vite dev server at http://localhost:5173
```

## Running Tests

```bash
cd backend
pytest                         # integration tests
ruff check .                   # lint
ruff format .                  # format
```

```bash
cd frontend
npm run build                  # type check + build
```

All tests must pass before a PR can be merged. CI runs `pytest` and `ruff check` on every push.

## Making a Contribution

1. Fork the repository
2. Create a feature branch (`git checkout -b my-feature`)
3. Make your changes
4. Ensure tests pass (`pytest` + `ruff check .`)
5. Submit a pull request

Keep PRs focused on a single change. Write clear commit messages that describe *why*, not just *what*.

## Conventions

See [CLAUDE.md](CLAUDE.md) for detailed coding conventions, project structure, and architecture decisions. The highlights:

- **No secrets in code.** Use environment variables for all credentials.
- **Async everything** on the backend (async SQLAlchemy, async FastAPI endpoints).
- **Service layer** for business logic. Routes should be thin.
- **SWR for data, Zustand for UI state** on the frontend.
- **Write tests alongside features**, not after.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
