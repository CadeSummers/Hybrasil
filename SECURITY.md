# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue:

- through GitHub's **Report a vulnerability** button on this repository's
  Security tab, or
- by email to <cade@hybrasil.app>.

Say what you found, how to reproduce it, and what it could affect. You will get
a reply within a week. Hybrasil is maintained by one person, so a fix may take
longer, but you will be kept informed, and credited if you wish once it is
fixed.

## What is in scope

- The site at <https://hybrasil.app> and the viewer's code in this repository.
- The Suggest Changes endpoint (`functions/api/suggestions.js`) and what it
  stores.
- `--serve`, the local web server, where a problem could reach beyond the
  machine running it.

Errors in the data itself are not security issues. Please send those through
Suggest Changes or a Data correction issue.

## Supported versions

Only the current `main` branch and the live site receive fixes.
