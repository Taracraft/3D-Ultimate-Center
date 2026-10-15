# Source distribution notices

These notices describe this repository source selection. Runtime installation
and distribution of engine executables or complete container images require
their own acceptance and artifact inventory.

## File-specific terms

| Material | Applicable notice |
| --- | --- |
| Inherited Studio sources and the unchanged legacy component | [MIT copyright and permission notice](LICENSE) |
| New original Slicer-Server material within its declared scope | [Custom private-use license](studio/Slicer-Server/LICENSE) |
| Selected original Bambu Studio profiles and derived profile data | [Upstream GNU AGPL version 3](studio/Slicer-Server/licenses/AGPL-BambuStudio.txt) |
| Mixed-origin provenance documents | Each included source retains its own terms; see the file map |

The complete inherited MIT text is also preserved in
[MIT-Studio.txt](studio/Slicer-Server/licenses/MIT-Studio.txt). Keep its copyright
and permission notice with inherited material and copies. A later folder label
does not withdraw permissions previously granted.

The custom license applies only to new original material authored for this
project in its stated scope. Imported/generated payloads, third-party
material and previously licensed material are excluded. Configuration and
user-created data retain the exceptions stated there. It is a custom
source-available license, not an Open Source license.

The [file map](source-license-map.json) identifies the notice boundary for each
delivered path. Source identities and dated project records support lineage;
they are not a certification of sole authorship.

## Selected Bambu Studio profile material

Upstream repository: bambulab/BambuStudio.
Revision: 42d319c6692fa8e64790fddf0cdaafd2a4254bcc.

The unchanged upstream AGPL text is included above. The 118 original
profile/include JSON texts used for 54 selections are preserved byte-exactly
in [PROFILE_SOURCE_BUNDLE.json](studio/Slicer-Server/PROFILE_SOURCE_BUNDLE.json),
with upstream paths, revision and Git object identities.

Modification notice, 2026-10-15: this source selection contains projections
and reconstructions of the upstream profile data in these local files:

- studio/deploy/homeassistant/custom_components/ultimate_3d_studio/native_filament_defaults.json
- studio/deploy/homeassistant/custom_components/ultimate_3d_studio/h2s_native_defaults.json

[PAYLOAD_PROVENANCE.json](studio/Slicer-Server/PAYLOAD_PROVENANCE.json) describes
the selection, 46 filament values, 12 first-element process-field projections
and eight sound/template reconstructions. Original texts, transformations and
the offline verifier are provided with this selection. These originals and
derived profile data are conveyed under the upstream AGPL terms, without the
custom private-use restrictions. Existing upstream notices remain intact.

This selection includes no engine executable, Bambu network plugin or engine
program source. It does not claim to be the full corresponding source for a
future engine binary or image. Packaging components separately does not itself
settle whether a future runtime combination is a covered combined work.

## Frontend and build tools

The inspected deployed frontend build manifest identifies 131 local Studio
frontend inputs. No npm package source appears in that manifest. esbuild and
TypeScript are build dependencies. Installed npm/Python tool binaries are not
part of this Git source inventory; dependency declarations and lockfiles are.
Distribution of those tools or library binaries requires notices for the
actual included artifacts.

## Scope of this review

The exact delivery manifest binds source bytes, baseline files and these
notices. The five native unit sources are included as source files; their
inclusion grants no service installation or execution approval. Existing
runtime package provenance flags remain conservative and are not changed by
this Git source notice inventory.

Engine binaries, plugins, runtime libraries and complete container images are
a later distribution scope. Their corresponding-source and SBOM obligations,
and real Linux/Docker/TLS/upgrade/restore/HACS acceptance, remain open.

Primary references:

- https://opensource.org/license/mit
- https://github.com/bambulab/BambuStudio/blob/42d319c6692fa8e64790fddf0cdaafd2a4254bcc/LICENSE
- https://github.com/bambulab/BambuStudio/blob/42d319c6692fa8e64790fddf0cdaafd2a4254bcc/README.md
- https://www.gnu.org/licenses/agpl-3.0.html
