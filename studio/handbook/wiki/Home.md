# Ultimate 3D Studio

![Promo-Illustration](https://raw.githubusercontent.com/Taracraft/3D-Ultimate-Center/main/studio/handbook/assets/studio-hero.png)

Ultimate 3D Studio führt Modellbearbeitung, Materialien, Druckvorbereitung und Druckerübersicht in Home Assistant zusammen. Du arbeitest auf einer virtuellen Druckplatte, bereitest Geometrie und Materialflächen vor und prüfst anschließend das Slicing-Ergebnis. Der separate Ultimate Slicer Server übernimmt die Berechnung der Druckbahnen.

Das Wiki führt durch einzelne Aufgaben. Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md) beschreibt den gesamten Arbeitsablauf und die Zusammenhänge ausführlicher. Der [Funktionskatalog](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/handbook/FEATURES.md) dient zum gezielten Nachschlagen vorhandener Werkzeuge.

## Dein passender Einstieg

| Du möchtest … | Beginne hier | Danach |
| --- | --- | --- |
| ein Modell vorbereiten | [Erste Schritte](Erste-Schritte.md) | CAD, Materialien, Vorschau |
| eine Installation planen | [Installation](Installation.md) | Slicer-Anbindung und Fehlerhilfe |
| am Projekt mitarbeiten | [Entwicklung](Entwicklung.md) | Architektur, Tests und Lizenz |

## Vom Modell zum geprüften Auftrag

Beginne mit einer überschaubaren STL-Datei oder einem Grundkörper. Kontrolliere zuerst die Abmessungen und die Auflage auf dem Druckbett. Wähle anschließend Drucker, Düse, Filament, Prozess und Plattenoberfläche. Speichere diesen Arbeitsstand, bevor du Bemalung oder umfangreiche Änderungen ausprobierst.

Für mehrere Teile helfen zusätzliche Druckplatten und eine eindeutige Objektbenennung. Mehrfarbenmodelle benötigen reale verfügbare Filamente und eindeutige Materialkanäle. Ein fertig bearbeitetes Modell wird erst durch einen passenden Slicing-Auftrag zu einem Druckergebnis mit Schichten und Bahnen. Prüfe dafür die [Vorschau](Vorschau.md).

## Voraussetzungen und Paketstand

Für CAD und Projektverwaltung benötigst du eine eingerichtete Studio-Oberfläche. Die Studio-Integration kann über HACS im normalen Repositorymodus bezogen werden. Verfügbare Versionen und Downloads stehen unter [Studio-Releases](https://github.com/Taracraft/3D-Ultimate-Center/releases). Die [Integrationsmetadaten](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/custom_components/ultimate_3d_studio/manifest.json) beschreiben den Quellstand im Hauptzweig; dieser kann vom letzten Release abweichen. Slicing setzt zusätzlich einen erreichbaren Server mit geeigneten Engines und Profilen voraus; die vollständige Engine-Runtime steht weiterhin aus. Konkrete Installations- und Funktionsnachweise werden getrennt vom veröffentlichten Quellstand dokumentiert.

Falls ein Schritt scheitert, sichere den Arbeitsstand und grenze den betroffenen Bereich mit der [Fehlerhilfe](Fehlerhilfe.md) ein. Das erwartete Ergebnis des Einstiegs ist ein nachvollziehbar vorbereitetes Projekt. Eine tatsächliche Druckfreigabe erfolgt gesondert.
