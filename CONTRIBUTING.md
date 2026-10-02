# Contributing

Thanks for your interest in improving this project! Contributions are welcome.

## How to contribute

1. **Fork** the repository and clone your fork.
2. Create a branch for your change: `git checkout -b feat/my-change`.
3. Make your changes, keeping them focused on a single topic.
4. Run the tests before committing:
   ```
   pip install -r requirements.txt -r requirements-dev.txt
   pytest
   ```
5. Commit with a clear message (e.g. `feat: add tyre temperature chart`, `fix: handle empty laps`).
6. Push to your fork and open a **Pull Request** against `main`.

## Rules

- `main` is protected: nobody can push to it directly. All changes go through a Pull Request approved by the maintainer.
- Keep PRs small and describe *what* changed and *why*.
- Do not commit large telemetry files (CSV) or secrets.
- By contributing, you agree that your work is released under the project's [MIT License](LICENSE).

## Reporting bugs and ideas

Open an issue with steps to reproduce (and a small sample of data if relevant), or describe the feature you would like to see.
