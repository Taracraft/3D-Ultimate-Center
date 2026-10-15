# Source and license boundaries

This repository is a component projection of the reviewed Ultimate 3D Studio
sources. Preserving paths and original bytes does not relicense those files.

- `LICENSE` preserves the prior Studio MIT notice. It is not a blanket claim
  that every file in this repository is MIT-licensed.
- New original material in `Slicer-Server/` retains the scoped custom terms in
  `Slicer-Server/LICENSE`, with the explicit exclusions written there.
- Imported/generated worker payloads, helpers and profile data retain their
  original applicable notices and are not newly assigned the custom license.
- `Slicer-Server/THIRD_PARTY_NOTICES.md`, `PAYLOAD_PROVENANCE.json`,
  `PROFILE_SOURCE_BUNDLE.json` and `licenses/` preserve component provenance,
  upstream profile identity and the accompanying license texts.
- Root README and this notice are delivered from their named Slicer-Server
  source documents; copying them to the root grants no broader rights.
- Native package, worker, deployment and test sources preserve the source
  licensing applicable in the original Studio tree. Previously granted rights
  and mandatory rights remain unaffected.
- Engines, Debian packages, base images and runtime libraries are not included
  as binaries here. Each needs its own provenance and licensing review before
  an engine-bearing image or release artifact is distributed.
- Historical `continuity/` records and the historical testserver package keep
  their original notices. The new source manifest does not silently approve
  those historical artifacts for production or as the current source package.

The source manifest records byte identity and component closure, not a legal
opinion, ownership determination or production deployment approval.
