# Build und Tests

Die Quellen werden mit Python-Tests und einer eigenen GitHub-Actions-Pipeline geprüft. Der Build-Kontext übernimmt eine feste Auswahl der benötigten Dateien.

```sh
python3 Slicer-Server/build_repository.py --verify .
python3 Slicer-Server/verify_profile_sources.py --source-root .
python3 -m pytest -q tests
```

Die Python-Abhängigkeiten stehen in `requirements-test.txt`. Für den Imagebau siehe [Docker-Schnellstart](../DOCKER_QUICKSTART.md); für isolierte Laufzeitprüfungen [Container-Tests](../CONTAINER_TESTING.md).
