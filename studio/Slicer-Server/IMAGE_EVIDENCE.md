# Gemeinsamer Quell-, Image- und Linux-Nachweis

`verify_image_evidence.py` verbindet die bereits vorhandenen Einzelpruefer.
Es liest ausschliesslich Dateien. Es startet weder Docker noch Engines,
installiert nichts und veraendert weder Nachweise noch die geprueften Quellen.

## Was der gemeinsame Vertrag prueft

1. Den explizit erwarteten Commit und den unabhaengig erwarteten SHA-256 des
   `slicer-source-manifest.json` pruefen. Alle darin aufgefuehrten Dateien
   werden bytegenau geprueft; Aliase muessen ihren Originalquellen entsprechen.
2. Genau vier Image-Nachweisdateien lesen: `image-build-result.json`,
   `source-check.json`, `resource-layout.json` und `target-image-sbom.json`.
   Wahlweise wird das urspruengliche CI-ZIP ohne Entpacken gelesen.
3. Das offizielle unveraenderliche Basisimage, Image-ID, Plattform, Commit,
   Quellmanifest und die drei enthaltenen Nachweisdateien zusammenbinden.
   Die in der Paketreferenz angegebene Dockerfile-Pruefsumme muss jetzt auch
   den tatsaechlich gelesenen Dockerfile-Bytes entsprechen.
4. Den bestehenden SBOM-Verifikator verwenden: Paketanzahl, Pflichtpakete,
   Architektur, Quellen-/Binaerversionen und Copyright-Pruefsummen muessen
   zum gleichen Image und zur gleichen Referenz gehoeren. Der Kontext wird
   mit dem vertrauenswuerdigen mitgelieferten Kontextbauer nur im Speicher
   rekonstruiert. Sein Hash und der Quell-Preflight muessen uebereinstimmen.
5. Einen optionalen Linux-Nachweis mit dem bestehenden Schema-5-Verifikator
   pruefen. Zusaetzlich muessen bestandene Compose-, API-/Worker-,
   Upgrade-Ausgangs- und Rollback-Imagebelege exakt dieselbe Image-ID tragen.
   Das vorangestellte `sha256:` wird nur an dieser fest definierten Grenze
   entfernt; Grossschreibung, Tags und Null-Digests werden nicht normalisiert.

Die Dateien werden am Ende erneut gelesen. Eine waehrend der Pruefung
beobachtete Aenderung wird abgewiesen. Symlinks, Junctions, mehrfach verlinkte
Dateien, Pfadrueckspruenge, doppelte JSON-Schluessel, uneindeutige Zahlen und
unerwartete Archivmitglieder werden abgewiesen. Eingaben sind groessenbegrenzt.
Vom Aufrufer gelieferte Python-Dateien werden nicht importiert oder ausgefuehrt.

## Image-Nachweis vor der abschliessenden Installation

Die Variablen `SOURCE_COMMIT` und `SOURCE_MANIFEST_SHA256` muessen aus dem
bereits vertrauten, unabhaengig geprueften Auslieferungs-/CI-Nachweis stammen,
nicht ausschliesslich aus dem gerade zu pruefenden ZIP. `checkout` bezeichnet
hier die vollstaendige Slicer-Quellprojektion dieses konkreten Commits.

```sh
python Slicer-Server/verify_image_evidence.py \
  --source-root checkout \
  --evidence target-image-evidence.zip \
  --expected-commit "$SOURCE_COMMIT" \
  --expected-manifest-sha256 "$SOURCE_MANIFEST_SHA256"
```

Anstelle des ZIPs darf `--evidence` auf ein Verzeichnis mit genau den vier
JSON-Dateien zeigen. Ohne Linux-Nachweis lautet dessen Status ausdruecklich
`not_run`. Das ist kein Fehler des Imagebaus und verhindert diesen
Teilabschluss nicht. Ein alter Build wird gegen seine erhaltene Quellprojektion
geprueft, niemals gegen einen spaeter veraenderten `main`-Checkout.

## Anschluss des spaeteren Linux-Testnachweises

Erst nach der abschliessenden Linux-Pruefung kommen diese drei Argumente
**gemeinsam** hinzu:

```sh
  --linux-evidence linux-evidence.json \
  --expected-package-archive-sha256 "$PACKAGE_ARCHIVE_SHA256" \
  --expected-package-manifest-sha256 "$PACKAGE_MANIFEST_SHA256"
```

Die beiden Paketpruefsummen stammen aus der gesonderten Paketpruefung.
Das Werkzeug prueft deren Bindung im Linux-Dokument, nicht erneut die Bytes
des Installationspakets. Phasenreihenfolge, Verkettung, Daten-/Profilkontinuitaet,
Supervisor- und TLS-Felder prueft weiterhin der vorhandene Linux-Verifikator.
Ein zwar intern konsistenter, aber zu einem anderen Image gehoerender
Linux-Nachweis wird nun zusaetzlich abgewiesen. Ein abgebrochener oder nur
teilweise durchgefuehrter Test wird nicht zu einer Gesamtabnahme aufgewertet.

## CI und Rueckgabecodes

Die Slicer-CI fuehrt den gemeinsamen Pruefer nach Imagebau und Belegbildung,
aber **vor** dem Upload der vier Nachweisdateien aus. Sie verwendet den von
GitHub ausgecheckten Commit und dessen Quellmanifest. Das Aggregatergebnis
liegt ausserhalb des Vier-Dateien-Verzeichnisses und wird im Job ausgegeben;
das bisherige Archivformat bleibt unveraendert. Der Zusatzschritt benoetigt
keine weiteren Berechtigungen, Tokens, Hostmounts oder Netzwerkzugriffe.

| Exitcode | Bedeutung |
| --- | --- |
| 0 | Image-/Quellbindung gueltig; kein Linux-Dokument geliefert oder dessen Vertrag vollstaendig |
| 2 | Image-/Quellbindung gueltig; mitgeliefertes Linux-Dokument teilweise oder blockiert |
| 1 | Eingabe, Identitaet, Integritaet oder Einzelvertrag abgewiesen |

`release_complete` und `production_approved` bleiben immer `false`.
Diese Felder sind keine vom Aufrufer umschaltbare Freigabe.

## Grenzen

Der Vertrag gilt fuer das gegenwaertige **Source-Preflight-Image ohne
Engine-Binaerdateien**. Ein Image mit installierten Engines oder einem
Registry-Push benoetigt einen entsprechend erweiterten, separat geprueften
Vertrag; Freigabefelder duerfen nicht einfach umgeschrieben werden.

Hashes erkennen Veraenderungen relativ zu vertrauenswuerdigen Referenzen.
Sie sind keine Signatur und beweisen nicht die Wahrheit beliebig selbst
verfasster Testberichte. Der Verifikator erhebt keine neuen Laufzeitmessungen.
Ein Upgrade-Zielimage braucht weiterhin seinen eigenen Paket-/Buildnachweis;
hier wird nur die gemeinsame Ausgangs- und wiederhergestellte Image-ID gebunden.
Der Schutz ist keine atomare Momentaufnahme gegen einen boesartigen Prozess
mit derselben Benutzeridentitaet. Betriebsprüfung, Enginefunktion,
Quellen-/Lizenzpflichten und vollstaendiger Produktrelease bleiben getrennt.

Die frische Linux-Neuinstallation bleibt der letzte Verifikationstest nach
dem ansonsten fertiggestellten Release. Ein erfolgreicher Image-Vertrag
allein erklaert nicht den gesamten Release fuer abgeschlossen.
