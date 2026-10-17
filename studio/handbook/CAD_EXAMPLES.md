# CAD-Beispiele

[Handbuch](../README.md) · [Funktionsübersicht](FEATURES.md) · [CAD-Wiki](https://github.com/Taracraft/3D-Ultimate-Center/wiki/CAD)

![Würfel, Zylinder, Ring und Kegel auf der Druckplatte](images/cad-plate.png)

Die Abbildung zeigt vier im Studio erzeugte Grundkörper. Der ausgewählte Kegel ist durch einen Rahmen und die Transformationsachsen markiert.

## Die Szene nachbauen

1. Ein leeres Projekt öffnen. Bestehende Änderungen vorher speichern.
2. Unter **Einfügen** einen Würfel, einen Zylinder, einen Ring und einen Kegel erstellen.
3. **Anordnen** verwenden und die Abstände auf der Druckplatte prüfen.
4. Mit **Alles einpassen** die gesamte Szene anzeigen. Über das Mausrad lässt sich der Ausschnitt vergrößern.
5. Den Kegel in der Objektliste auswählen und Position oder Abmessungen bearbeiten.

Die Grundkörper bleiben eigenständige Modelle. Ihre Materialzuordnung wird unter **Materialien** festgelegt; das Erzeugen der Geometrie startet keinen Druck.

## Arbeitsbereich

![Werkzeugleisten, Objektliste, Druckplatte und Prozessoptionen](images/cad-overview.png)

Links stehen Modelle und Malbereiche, in der Mitte die Druckplatte, rechts die Prozessoptionen. Werkzeugleisten lassen sich einklappen, um mehr Platz für das Modell zu schaffen. Die dargestellten Profilwerte sind Beispiele aus der abgebildeten Installation und müssen an den eigenen Drucker angepasst werden.

Die Aufnahmen zeigen die Oberfläche vom Oktober 2026. Einzelne Bedienelemente können sich im weiteren Entwicklungsverlauf ändern.

## Einen Ring oder Hohlkörper geometrisch teilen

1. Genau ein sichtbares Objekt auswählen und **Geometrisch sicher teilen** öffnen.
2. **Achse** und **Position (mm)** der Trennebene festlegen. Die Position bezieht sich auf den Arbeitsbereich, auch wenn das Objekt gedreht ist.
3. **Teilung prüfen** wählen. Erst eine gültige Vorschau schaltet **Als zwei Objekte übernehmen** frei.
4. Die beiden Ergebnisobjekte und ihre Materialvorschau kontrollieren. **Abbrechen** lässt das Quellobjekt unverändert.

Der Schnitt schließt auch konkave Querschnitte, Öffnungen und darin liegende Inseln. Bei einem waagerecht geschnittenen Ring bleibt die zentrale Öffnung erhalten; bei einem Hohlkörper wird nur dessen Materialquerschnitt geschlossen. Bestehende Materialflächen und Malebenen werden auf die Ergebnisobjekte übertragen. Neue Innenflächen erhalten die Objektzuordnung und sollten vor dem Slicen in der Materialvorschau geprüft werden.

Offene oder widersprüchlich orientierte Modelle, sich schneidende oder berührende Konturen und nicht eindeutig schließbare Schnittflächen werden abgewiesen. Wähle dann eine andere Ebene oder prüfe das Ausgangsmodell. Sehr komplexe Konturen können ebenfalls abgelehnt werden. Die Kappenprüfung berücksichtigt die Rundungsgenauigkeit der Modellkoordinaten; sie verändert die vorhandenen Randpunkte nicht.
