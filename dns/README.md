# WOODERA DNS bridge

This directory contains a deliberately restricted Beget DNS synchronization script for `woodera-studio.ru`.

## Files

- `desired.json` — approved DNS target state for GitHub Pages.
- `sync_beget.py` — calls only the Beget API methods needed to read/update DNS and create the `www` subdomain.

## Required GitHub repository secrets

Create two Actions repository secrets:

- `BEGET_LOGIN`
- `BEGET_PASSWORD`

Use a dedicated Beget API password as the value of `BEGET_PASSWORD`, not the normal Beget account password.

## Workflow

The GitHub Actions workflow should check out the repository and run:

`python3 dns/sync_beget.py`

with the two repository secrets mapped to environment variables with the same names. The script refuses to operate on any domain except `woodera-studio.ru`, verifies the four approved GitHub Pages IPv4 addresses, preserves the current root MX/TXT records, and sets `www.woodera-studio.ru` to `miay2775.github.io`.
