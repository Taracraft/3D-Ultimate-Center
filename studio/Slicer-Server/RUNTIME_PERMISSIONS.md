# Container-Dateirechte

Status: lokale Linux-Rechtevergabe implementiert und mit synthetischen
Dateien geprueft. Noch keine gestartete Containerinstallation und kein
fertiger HA-Assistent. Der Code gehoert zum Hostinstaller.

## Fester Rechtevertrag

Die Compose-Kandidaten verwenden fuer API und Worker UID/GID 65532.
grant_runtime_access in host_storage.py richtet ausschliesslich die beiden
bereits provisionierten Verzeichnisse data und profiles ein.

| Bereich | Eigentuemer und Modus | Containerzugriff |
| --- | --- | --- |
| Basis und Engine-Store | unveraendert installer-privat | Nicht als Ganzes mounten |
| data, profiles | root:65532, 2770 | Gruppe darf lesen, schreiben und betreten |
| Ausgewaehlte Engine-Generation | unveraendert installer-eigen, Dateien 0644/0755 | Nur diese Generation read-only mounten |
| Steuerablage und Belege | unveraendert privat, Dateien 0600 | Nicht an API oder Worker weiterreichen |

Die Setgid-Markierung vererbt die Gruppe auf neue Eintraege. Die Stammordner
bleiben root-eigen: der Worker kann ihre Rechte nicht selbst erweitern.
Dateimodi neuer Inhalte haengen weiterhin von Anwendung und umask ab;
diese Operation schreibt keine vorhandenen Dateibaeume rekursiv um.

Die Basis bleibt privat. Docker bindet einzelne freigegebene Unterordner
ein; es muss der vertrauenswuerdige Hostdienst mit passenden Hostrechten
sein. Rootless Docker und User-Namespace-Remapping brauchen einen eigenen
UID/GID-Vertrag und sind durch diesen Schritt nicht freigegeben.

## Ablauf

1. Linux und lokale root-Rechte nachweisen; keine frei waehlbare UID/GID.
2. Gemeinsame Installationssperre nehmen und VolumeGuard pruefen.
3. Vertrauenswuerdiger Hostadapter muss gestoppte Worker bestaetigen.
   Danach Volume und leere Daten-/Profilstammordner nochmals pruefen.
4. Externen PERMISSIONS.json-Beleg im Zustand preparing dauerhaft schreiben.
5. Nur die zwei geoeffneten Verzeichnisdeskriptoren auf root:65532 und 2770
   setzen. Symlinks und POSIX-ACLs sind nicht zulaessig.
6. Volume, Rechte und Bindung nachpruefen, ready dauerhaft setzen und
   abschliessend VolumeGuard ausfuehren.

Der Beleg bindet den Digest der vorhandenen VOLUME.json. Datenpfad,
Dateisystemidentitaet und Rechtefreigabe sind damit gekoppelt. Unbekannte
Felder, falsche Typen, abweichende Gruppe/Modi oder ein alter Volume-Digest
werden abgewiesen. Der Gruppen-Schreibzugriff gilt nur fuer die exakt
gebundenen data/profiles-Stammordner, niemals fuer Vorfahren oder Engines.

Ein fertig eingerichteter Aufruf ist nur lesend wiederholbar und erhaelt
Benutzerdaten. Vor der allerersten Rechtevergabe muessen beide Verzeichnisse
leer sein. Bestehende Profile oder Modelle werden nicht automatisch
uebernommen, umgeschrieben oder geloescht.

## Abbruch und Rueckweg

Nach einem Fehler hinter dem preparing-Beleg bleibt der Zustand gesperrt.
Auch wenn ein Ordner bereits angepasst wurde, akzeptiert VolumeGuard keine
teilfertige Freigabe. Eine Wiederholung repariert oder adoptiert sie nicht
stillschweigend. Der lokale Administrator muss bei weiterhin gestoppten
Workern Volume, beide Ordner und Beleg abgleichen. Automatische Recovery
fuer diese Rechteoperation ist noch offen. Kein pauschales rekursives
chmod/chown als Reparatur verwenden.

Die Pruefungen sind keine atomare Sperre gegen einen privilegierten,
parallel handelnden Hostadministrator. Die gemeinsame Dateisperre gilt
fuer kooperierende Installeroperationen. Ein Worker darf weder den
privaten Elternpfad noch den externen Berechtigungsbeleg veraendern.

## Nachweise

Windows: gemeinsam mit Speicheradapter und Installer 61 Tests bestanden,
20 Linux-/POSIX-Faelle ausgelassen, 27 Untertests bestanden.
Linux: 50 Speicher-/Rechtefaelle ohne Skip bestanden. Enthalten sind
tatsaechliche UID/GID-Wechsel eines kurzlebigen Testprozesses in einem
temporaeren Dateibaum: Schreiben in Daten/Profile erlaubt, Rechteaenderung
am Stammordner und Zugriff auf private Steuerdateien verboten; synthetische
Engine-Dateien lesbar, aber weder ueberschreibbar noch erweiterbar.

Weitere Faelle: veraenderte Eigentuemer/Gruppe/Modi, falscher Beleg,
abgebrochene Teilvergabe, konkurrierende Sperre, POSIX-ACL und fremde Inhalte.
Kein echter Worker, keine Engine, kein Container, kein Dienst, kein
produktiver Datenpfad und kein Druckauftrag wurde gestartet oder veraendert.

## Noch offene Installation

Die Compose-Datei mountet derzeit data und eine ausgewaehlte Engine-Generation.
Die getrennte profiles-Ablage muss noch mit dem tatsaechlichen Profilverbraucher
verdrahtet werden; nur ein zusaetzlicher Mount ohne Verbraucher waere unvollstaendig.
Auch Dateninitialisierung, Token-/TLS-Dateirechte, gesicherte Hostkopplung,
Lifecycle/Health/Rollback und HA-Einrichtungsflow bleiben weitere Schritte.
Der Stop-Callback ist ein lokaler Adaptervertrag, noch kein implementierter
Docker-/Supervisor-Stopp. Alle echten Engine-Releases bleiben pending und
container_deploy_ready bleibt false.
