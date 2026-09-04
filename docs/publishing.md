# Publishing LEA to PyPI

LEA uses PyPI Trusted Publishing (OIDC). The repository does not store a PyPI
password or API token, and the build job cannot mint a publishing credential.

## One-time setup

1. Sign in to PyPI and add a pending trusted publisher for the project name
   `lea-agent`.
2. Enter these GitHub details exactly:

   | PyPI field | Value |
   | --- | --- |
   | Owner | `charlesenchine-arch` |
   | Repository | `Light-weight-Ensemble-Agent` |
   | Workflow | `publish.yml` |
   | Environment | `pypi` |

3. In the GitHub repository, create an environment named `pypi`. Add required
   reviewers and restrict it to the branch from which maintainers dispatch the
   workflow (normally `main`) if the repository plan supports protection rules.

PyPI can create the `lea-agent` project on its first successful publish through a
pending publisher. Do not add `PYPI_API_TOKEN`, a password, or a username to this
workflow.

## Publish an existing release

1. Confirm CI is green for the release tag and that the GitHub Release contains
   the matching wheel and source archive.
2. Open **Actions → Publish to PyPI → Run workflow**.
3. Enter the exact existing tag, such as `v0.3.0`.
4. Review and approve the `pypi` environment deployment.
5. Confirm the package and attestations appear at
   <https://pypi.org/project/lea-agent/>.

The workflow rejects malformed tags and tags whose value does not match the
version in `pyproject.toml`. It builds in an unprivileged job, transfers only the
resulting distributions, and grants OIDC permission solely to the publish job.

## Before the next release

- Update the version in `pyproject.toml` and the changelog.
- Run `python -m ruff check agentflow tests` and `python -m pytest`.
- Run `python -m build` and inspect both distributions.
- Create and push the matching `vX.Y.Z` tag.
- Publish the GitHub Release before dispatching the PyPI workflow.

Official references:

- [PyPI trusted publishers](https://docs.pypi.org/trusted-publishers/)
- [PyPA publish action](https://github.com/pypa/gh-action-pypi-publish)
- [GitHub OIDC for PyPI](https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-pypi)
