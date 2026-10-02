# Recovery status

Updated: 2026-10-02

Completed source groups:
- studio-v6/api: complete
- studio-v6/core: complete
- studio-v6/frontend: all source paths represented
- printer_control_center Python/YAML root: complete
- printer_slicing_server Home Assistant component: complete
- ultimate_3d_studio_v6 root and network_plugin: substantially complete
- native slicing server: main application, profiles, engine config, web UI and service definitions recovered

Validation:
- Python compile check passes in GitHub Actions.
- Frontend dependency installation passes.
- TypeScript validation currently stops at studio-v6/frontend/studio-mega-workspace-v2.ts because the repository copy was truncated during transport. The canonical Homeassist source is 172531 bytes and remains intact on the VM.

Still to close:
- replace the truncated oversized frontend file with the canonical VM copy
- recover remaining tests rejected by the connector safety filter
- recover remaining build/deploy/documentation files rejected by the connector safety filter
- add remaining non-secret binary assets
- capture sanitized Lovelace dashboards
- verify Bambu Studio engine acquisition and checksum
- run clean-machine rebuild and end-to-end verification

Never commit logs, credentials, passwords, tokens, cookies, private keys or Home Assistant authentication storage.
