# Contributing

Thanks for helping improve this project.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Contribution workflow

1. Create a feature branch.
2. Keep changes focused and small.
3. Run the relevant tests before opening a pull request.
4. Submit a PR with a clear description.

## Security expectations

- Keep all examples within the simulated, local-only lab environment.
- Do not introduce real-world hardware, payment data, or offensive tooling into the project.
- Maintain the fail-secure design and audit-friendly behavior.
