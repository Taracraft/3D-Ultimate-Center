# Build und Tests

Ab Wurzel des eigenständigen Repos:

```bash
python3 Slicer-Server/build_repository.py --verify .
python3 Slicer-Server/verify_profile_sources.py --source-root .
python3 -m pytest -q tests
```

Vorher die gepinnten Test-Abhängigkeiten aus `requirements-test.txt` in einer
eigenen virtuellen Umgebung installieren. Keine echten Dienste, Engines,
HA-Installationen oder Drucker für diese Quelltests verwenden.

Die eigene GitHub-CI verifiziert Manifest und Offline-Profilquellen, führt
die Komponententests aus und baut Native-/Docker-Kontext-/Testserver-Pakete
in einem neuen temporären Verzeichnis außerhalb des Klons. Danach werden die
Quellidentitäten erneut geprüft. Das ist keine echte Engine-Betriebsabnahme.

[Docker Schritt für Schritt](../DOCKER_QUICKSTART.md) ·
[Manuelle Linux-Abnahme](../LINUX_TEST_SERVER_RUNBOOK.md) ·
[Release-Grenzen](Release-Abnahme.md).
