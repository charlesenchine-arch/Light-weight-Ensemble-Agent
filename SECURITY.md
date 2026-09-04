# Security policy

## Supported versions

LEA is currently pre-1.0. Security fixes are applied to the latest release and the
default branch.

## Reporting a vulnerability

Please do not open a public issue for vulnerabilities involving command execution,
workspace boundary bypass, secret exposure, prompt injection that crosses the policy
boundary, or provider credential handling.

Use GitHub's **Report a vulnerability** flow under the repository Security tab. Include:

- the affected version or commit;
- operating system and Python version;
- a minimal reproduction;
- expected and observed policy behavior;
- whether credentials or files outside the workspace were exposed.

You should receive an acknowledgement within seven days. A fix timeline depends on
severity and reproducibility. Please allow time for a patch before public disclosure.

## Operational guidance

- Keep API keys in environment variables or `.env`; never commit them.
- Run LEA in a version-controlled workspace.
- Inspect diffs before executing or publishing generated code.
- Keep `allow_paths` narrow and remove entries that are no longer needed.
- Treat third-party model output and harvested skills as untrusted input.
