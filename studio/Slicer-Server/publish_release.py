"""Publish the reviewed source release from successful same-repository main CI.

No packaging, runtime execution, tag inventory, credential export or overwrites.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://api.github.com"
SPECS = {
    "Taracraft/3D-Ultimate-Center": {
        "workflow": "Studio source contract",
        "workflow_path": ".github/workflows/studio-source-contract.yml",
        "version_path": "homeassistant/custom_components/ultimate_3d_studio/manifest.json",
        "version": "6.0.7",
        "name": "Ultimate 3D Studio",
        "prerelease": False,
        "contents": "Home-Assistant-Integration, gebautes Studio-Frontend, CAD-/Profilquellen, Handbuch und Wiki-Quellen.",
    },
    "Taracraft/3D-Ultimate-Slicer-Server": {
        "workflow": "Slicer source contract",
        "workflow_path": ".github/workflows/slicer-source-contract.yml",
        "version_path": "packages/ultimate-slicer-server/release.json",
        "version": "0.1.0-alpha12",
        "name": "Ultimate Slicer Server",
        "prerelease": True,
        "contents": "API-/Workerquellen, Container- und Paketwerkzeuge, geprüfte Profilquellen, Installations- und Betriebsdokumentation sowie Wiki-Quellen.",
    },
}


class PublicationError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubAPI:
    def __init__(self, token):
        if not token:
            raise PublicationError("GITHUB_TOKEN fehlt.")
        self.token = token
        self.opener = build_opener(NoRedirect)

    def __call__(self, method, path, body=None, allow_missing=False):
        if not path.startswith("/repos/Taracraft/") or ".." in path:
            raise PublicationError("Nicht erlaubter API-Pfad.")
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(API + path, data=data, method=method, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "ultimate-studio-release",
        })
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404 and allow_missing:
                return None
            # Never log the token, request headers or arbitrary response payload.
            state = "Ergebnis unbekannt" if method == "POST" and (error.code >= 500 or error.code == 408) else "abgewiesen"
            raise PublicationError(f"GitHub {method} {state}: HTTP {error.code}. Keine Wiederholung oder Überschreibung; manuell abgleichen.") from None
        except OSError:
            raise PublicationError(f"GitHub {method}: Ergebnis unbekannt nach Netzwerkfehler. Keine Wiederholung; Tag/Release manuell abgleichen.") from None


def check_run(run, repository, spec, expected_sha):
    expected = {
        "status": "completed", "conclusion": "success", "head_branch": "main",
        "name": spec["workflow"], "path": spec["workflow_path"], "head_sha": expected_sha,
    }
    if any(run.get(key) != value for key, value in expected.items()):
        raise PublicationError("Der Quell-CI-Lauf entspricht nicht dem geprüften main-Stand.")
    if run.get("event") not in {"push", "workflow_dispatch"}:
        raise PublicationError("Pull-Request- oder fremder Auslöser ist nicht releaseberechtigt.")
    if any(run.get(key, {}).get("full_name") != repository for key in ("repository", "head_repository")):
        raise PublicationError("Quell-CI stammt nicht vollständig aus diesem Repository.")


def check_release(release, repository, spec, sha, tag):
    expected_url = f"https://github.com/{repository}/releases/tag/{quote(tag, safe='')}"
    if (release.get("tag_name") != tag or release.get("draft") is not False
            or release.get("prerelease") is not spec["prerelease"]
            or release.get("target_commitish") != sha or release.get("html_url") != expected_url):
        raise PublicationError("Releaseobjekt passt nicht zu Version, Commit, Veröffentlichungsstatus oder URL; manuell abgleichen, nichts überschreiben.")


def publish(event, env, root, api):
    repository = env.get("GITHUB_REPOSITORY")
    spec = SPECS.get(repository)
    if spec is None or env.get("GITHUB_EVENT_NAME") != "workflow_run":
        raise PublicationError("Nur der festgelegte workflow_run-Auslöser ist erlaubt.")
    if env.get("GITHUB_REF") != "refs/heads/main" or env.get("GITHUB_API_URL", API) != API:
        raise PublicationError("Nur GitHub.com und main sind releaseberechtigt.")
    sha = env.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise PublicationError("Ungültige Commitbindung.")
    if event.get("action") != "completed" or event.get("repository", {}).get("full_name") != repository:
        raise PublicationError("Ungültiger Abschlussauslöser.")
    run = event.get("workflow_run", {})
    check_run(run, repository, spec, sha)
    run_id = run.get("id")
    if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
        raise PublicationError("Ungültige Quell-CI-Kennung.")
    base = "/repos/" + repository
    live_run = api("GET", f"{base}/actions/runs/{run_id}")
    check_run(live_run, repository, spec, sha)
    if live_run.get("id") != run_id or live_run.get("run_attempt") != run.get("run_attempt"):
        raise PublicationError("Der CI-Lauf wurde seit dem Auslöser ersetzt oder erneut gestartet.")
    version = json.loads((Path(root) / spec["version_path"]).read_text(encoding="utf-8-sig")).get("version")
    if version != spec["version"]:
        raise PublicationError("Versionsmetadaten passen nicht zur freigegebenen Veröffentlichung.")
    tag = "v" + version
    existing = api("GET", f"{base}/releases/tags/{quote(tag, safe='')}", allow_missing=True)
    if existing is not None:
        check_release(existing, repository, spec, sha, tag)
        return {"state": "existing_unchanged", "tag": tag, "commit": sha, "url": existing["html_url"], "prerelease": existing["prerelease"]}
    head = api("GET", f"{base}/git/ref/heads/main")
    if head.get("object", {}).get("sha") != sha:
        raise PublicationError("main hat sich verändert; keine Veröffentlichung eines veralteten CI-Stands.")
    # Atomic creation rejects an existing tag. Never inventory, move, delete,
    # force-update or work around a tag collision with another name.
    created = api("POST", f"{base}/git/refs", {"ref": "refs/tags/" + tag, "sha": sha})
    if created.get("ref") != "refs/tags/" + tag or created.get("object", {}).get("sha") != sha:
        raise PublicationError("Taganlage konnte nicht exakt bestätigt werden; manuell abgleichen.")
    body = (
        f"Veröffentlichter Quellstand: `{sha}`.\n\n"
        f"Enthalten: {spec['contents']}\n\n"
        "Externe Bedien-/Systemabnahmen und Testinstallationen sind aus der Releasebewertung ausgenommen. Nicht ausgeführte Prüfungen bleiben ungeprüft.\n\n"
        "GitHub stellt die Quellarchive des Tags automatisch bereit. Diese Veröffentlichung erzeugt kein zusätzliches ZIP und startet keine Anwendung oder Slicing-Engine.\n\n"
        "Freigegebene Engine-Binärpakete und eine installierbare Supervisor-App-Referenz sind in diesem Stand nicht enthalten. Davon abhängige Installationsaktionen bleiben gesperrt. Ein vollständiges Slicer-Laufzeitimage wird damit nicht behauptet.\n\n"
        f"Quellprüfung: https://github.com/{repository}/actions/runs/{run_id}\n"
        f"Dokumentation: https://github.com/{repository}/blob/{sha}/README.md\n"
        f"Wiki: https://github.com/{repository}/wiki\n"
    )
    if repository == "Taracraft/3D-Ultimate-Center":
        body += "\nHACS verwendet den normalen Tagmodus mit custom_components/ultimate_3d_studio; ein separates HACS-Release-ZIP wird nicht benötigt.\n"
    release = api("POST", f"{base}/releases", {
        "tag_name": tag, "target_commitish": sha, "name": f"{spec['name']} {version}",
        "body": body, "draft": False, "prerelease": spec["prerelease"],
        "generate_release_notes": False, "make_latest": "false" if spec["prerelease"] else "true",
    })
    check_release(release, repository, spec, sha, tag)
    return {"state": "created", "tag": tag, "commit": sha, "url": release.get("html_url"), "prerelease": release["prerelease"]}


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    result = publish(event, os.environ, Path.cwd(), GitHubAPI(os.environ.get("GITHUB_TOKEN")))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (PublicationError, OSError, ValueError, KeyError) as error:
        print("Release abgebrochen: " + str(error), file=sys.stderr)
        sys.exit(1)

