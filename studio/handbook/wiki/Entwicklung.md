# Entwicklung

Die Quellen liegen im Gesamtrepository unter `studio/`. Das Frontend verwendet TypeScript; die Integration und Slicer-Werkzeuge verwenden Python.

```sh
npm ci
npm run typecheck
npm test
python -m pytest -q
```

Die Python-Abhängigkeiten und Plattformunterschiede sind in [CI_DEPENDENCIES.md](../../CI_DEPENDENCIES.md) beschrieben. [ARCHITECTURE.md](../../ARCHITECTURE.md) erklärt die Komponenten. Die CI prüft Quellcode, Build und Dateimanifeste; Engine-Laufzeit und physische Drucker benötigen eigene passende Umgebungen.

Für Änderungen an gemeinsam verwendeten Slicer-Modulen auch deren Komponentenpaket prüfen. Generierte Dateien sind nicht die führenden Quellen.
