# Architektur

Der Slicer-Server trennt den Empfang von Aufträgen von ihrer Ausführung. Die HTTP-API nimmt Anfragen entgegen und verwaltet den Auftragszustand. Der Worker verarbeitet die Aufträge in einem eigenen Container ohne Netzwerkzugang. Diese Aufteilung bestimmt, wo Verbindungen geprüft werden und welche Dateien für die Verarbeitung erreichbar sein müssen.

## Voraussetzungen und Grenzen

Die Compose-Konfiguration unterscheidet Initialisierung, API und Worker. Engine- und Profilverzeichnisse werden schreibgeschützt in die Laufzeit eingebunden. Konfiguration, Eingaben und Ergebnisse liegen außerhalb des Images. Der Docker-Socket gehört nicht in diese Laufzeitcontainer. Änderungen an der Containerkonfiguration müssen diese Trennung erhalten.

| Bestandteil | Aufgabe | Bei der Prüfung beachten |
| --- | --- | --- |
| Initialisierung | Vorgesehene Laufzeitumgebung vorbereiten | Vorbereitung nicht mit erfolgreicher Auftragsverarbeitung gleichsetzen |
| API | Anfragen und Aufträge verwalten | Verbindung, TLS und Authentifizierung prüfen |
| Worker | Aufträge mit den bereitgestellten Engines verarbeiten | Engine-Dateien, Profile und benötigte Datenzugriffe prüfen |
| Persistente Ablagen | Konfiguration und Nutzdaten erhalten | Lebenszyklus unabhängig vom Image behandeln |

## Einen Auftrag durch die Architektur verfolgen

1. Prüfe, ob der Client die vorgesehene API-Adresse erreicht und dem TLS-Zertifikat vertraut.
2. Prüfe, ob die Authentifizierung zur eingerichteten Verbindung passt.
3. Ordne den Auftrag der benötigten Engine und den passenden Profilen zu.
4. Prüfe, ob der Worker die vollständigen Dateien lesen und Ergebnisse in der vorgesehenen Ablage ablegen kann.
5. Bewerte den tatsächlich beobachteten Auftragsausgang gemeinsam mit dem gemeldeten Dienstzustand.

Das erwartete Ergebnis ist eine durchgängige Zuordnung von Anfrage, Verarbeitung und Ergebnis. Ein erfolgreicher API-Aufruf bestätigt dabei weder den vollständigen Engine-Bestand noch korrekte Worker-Berechtigungen. Ebenso belegt ein vorhandenes Engine-Archiv noch keine erfolgreich ausgeführte Engine.

## Fehler eingrenzen

Bei Verbindungsfehlern beginnt die Untersuchung auf der API-Seite. Bei angenommenen, aber fehlgeschlagenen Aufträgen folgen Engine-Bestand, Profile, Mounts und Schreibrechte. Netzwerkzugriff im Worker einzuschalten oder den Docker-Socket einzubinden wäre eine Architekturänderung und ersetzt keine Ursachenklärung. Die [Fehlerdiagnose](Fehlerdiagnose.md) hilft bei der Reihenfolge.

Für konkrete Konfigurationswerte gelten die [Laufzeitinstallation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/RUNTIME_INSTALLATION.md) und die [Berechtigungsdokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/RUNTIME_PERMISSIONS.md). Zusammenhängende Abläufe stehen im [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md). Die beschriebene Architektur ist ein Konfigurationsvertrag; die tatsächliche Isolation einer Installation muss am Zielsystem gesondert nachgewiesen werden.
