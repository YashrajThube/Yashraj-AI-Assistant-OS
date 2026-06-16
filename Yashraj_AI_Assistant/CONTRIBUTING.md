# Contributing

Thanks for your interest in contributing to Yashraj AI Assistant. We welcome issues, suggestions, and pull requests.

Getting started

1. Fork the repository and clone your fork locally.
2. Create a Python virtual environment and install dev dependencies:

```powershell
python -m venv .venv
& .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Creating a branch

- Use feature branches named with the pattern: `feature/<short-description>` or `fix/<short-description>`.
- Create the branch from the main branch:

```bash
git checkout -b feature/my-feature
```

Running tests

- Run the test suite from the repository root:

```powershell
$env:PYTHONPATH='backend'
python -m pytest -q
```

Code style

- Follow PEP8 for Python. Use `black`/`isort` for formatting (not required but recommended).
- JavaScript/React: follow ESLint rules configured in the `frontend` folder.

Pull request process

1. Open a pull request against `main`.
2. Include a descriptive title and summary of the change.
3. Maintain small, focused PRs; add tests for bug fixes or new features.
4. CI will run tests and frontend build. Address any failing checks.

Thanks — your contributions make this project better!
