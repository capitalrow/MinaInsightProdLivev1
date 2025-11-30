# CI Workflow Triggers and Why Tests Run on Commit

## Why workflows start
- GitHub Actions workflows in `.github/workflows` are configured to run on `push` and `pull_request` events targeting `main` or `develop` (see `ci.yml`, `test.yml`, and related files). Any commit you push to those branches triggers the defined test suites automatically.
- Branch protection rules may require these workflows to pass before merges, so pushes or PR updates start the runs even if only docs change.

## Which workflows
- `ci.yml`: full test suite with Python + Node setup, database init, and unit/integration coverage.
- `test.yml`, `accessibility-tests.yml`, `e2e-tests.yml`, and `performance.yml`: additional matrices that may be wired to the same triggers depending on repository settings.

## How to avoid unintended runs
- Develop on feature branches and push there; workflows will still run on PR but not on every local commit unless you push.
- Use draft PRs to control visibility while still allowing CI to validate when needed.
- If you only need local validation, run tests with `pytest`/`npm test` locally without pushing, so CI is not triggered.
