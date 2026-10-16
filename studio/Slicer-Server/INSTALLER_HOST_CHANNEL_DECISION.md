# Installer Host Channel Decision

> Aktualisierung 16.10.2026: Die folgenden festen Core-Mountanforderungen
> beschreiben den bisherigen provisionierten Hostkanal, nicht eine allgemeine
> Voraussetzung des neuen Supervisor-App-Einrichtungswegs. Dieser wird über
> den HA-eigenen Supervisor-Client getrennt umgesetzt; Compose bleibt unabhängig.
> Keine frühere Schutzgrenze und kein zuvor abgewiesener Helfer wird dadurch
> umgangen. App-Laufzeit/Workerisolation bleiben separat nachzuweisen.
> Siehe [Supervisor-App-Einrichtung](SUPERVISOR_APP_SETUP.md).


Status: W41 design decision, source/documentation only. No host provisioning,
HA source sync, runtime change, installation or migration was performed.

## Decision

Keep the existing fixed AF_UNIX STI1 installer transport as the candidate
local IPC. It already separates control and mutation lanes, authenticates
bounded requests, checks SO_PEERCRED, pins the server identity on the HA
client, and does not expose a TCP listener. Do not add a second transport.

The channel is not deployable in the inspected HA VM. W40 found no installer
or handoff mount, no native installer service, HA Core uid 0 without a user
namespace, and a writable /share. Therefore no peer UID or mount security
claim is accepted yet.

## Candidate host-provisioning contract

A future host provisioner must deliver three distinct resources:

1. A pin record from a protected, read-only host provisioned source. It
   supplies host_id, server_uid, socket_directory and handoff_directory to
   decode_installer_endpoint as independent expected values.
2. The fixed installer socket directory, exposing only control.sock and
   mutation.sock to the HA client. The host server remains non-root and
   enforces its separately provisioned client UID/GID, token scopes and
   operation lanes.
3. The handoff directory, separately permissioned for the one-time token
   read, private HA credential readback and exact-inode cleanup. It must not
   share a writable parent with the pin source.

The runtime may not derive paths or expected identities from UI fields,
ConfigFlow values, request data or the handoff token. /share is not a pin
source. Docker socket access and an alternate TCP listener are not fallback
solutions.

## Required Linux proof before HA lifecycle wiring

- Read back mountinfo for each resource; prove the pin mount is read-only and
  the socket/handoff mounts have only the access they require.
- Record owner, group, mode, type and inode for the directories, sockets,
  pin file and handoff file; reject symlinks and unexpected ownership.
- Connect from the actual HA Core container and measure SO_PEERCRED on both
  ends. Measure the server UID and client UID; do not infer either from
  docker inspect or id alone. Verify the same values after a Core
  recreation/restart.
- Exercise authenticated preflight and read-only status only. Confirm wrong
  pins, wrong peer, wrong lane, expired credentials and absent mounts fail
  closed. No initialize/stage/activate, Docker, engine, job or printer action.
- Prove the provisioner recreates the contract after a supported host restart
  without changing HA Core or opening a broad Docker API.

If the current host cannot provide those mounts and peer identities through
its supported lifecycle, keep the HA installer setup unavailable and record
the host channel as blocked. Do not simulate success with writable storage.

## Scope boundary

This decision does not execute or revise the HAOS migration. It does not
establish a supported deployment target, container_deploy_ready, HA source or
live readiness, HACS acceptance, Linux installer acceptance, or pilot
approval. HA OptionsFlow and __init__.py wiring remain after the Linux proof.

## W42 source interface

The fixed HA-side files are /run/ultimate-slicer-server/pins/expected.json
for the root-owned pin record, /run/ultimate-slicer-server/installer/endpoint.json
for the service-owned endpoint descriptor, and
/run/ultimate-slicer-server/handoff for the one-time credential handoff.
The pin and endpoint directories must be separate read-only bind mounts.
The handoff directory is a third, separately permissioned read-write mount.
The source loader checks mountinfo, exact mount points, distinct mount IDs,
file type, link count, size, owner, mode and opened inode before decoding.

This interface is source-only. The current HA VM has not provisioned these
mounts. Do not wire it into HA setup until the actual Linux mount and
SO_PEERCRED tests pass.


## W43 source hardening

The HA-side mount resolver rejects equally specific mountinfo entries instead
of selecting one by file order. This covers stacked mounts at each fixed trust
path and remains a synthetic source check; actual Linux mountinfo, ownership,
mode, inode and both SO_PEERCRED measurements are still required before HA
lifecycle wiring.


## W44 Supervisor provisioning evidence

The current official App configuration documents map as selected
Supervisor-managed directory types mounted into an App container; its optional
path is the destination inside that App. The documented Core options API
lists no arbitrary bind-mount field. These references do not establish a
supported way to inject the three W42 fixed mounts into the running Core
container.

This is a blocker for HA flow wiring, not approval to change transport. Keep
the AF_UNIX candidate and the no-share/no-Docker-socket/no-TCP-fallback rules.
Before wiring, either provide a supported host provisioning path with measured
mount and peer evidence, or review the channel contract as a separate design
decision. No HAOS migration was performed.

Sources:
- https://developers.home-assistant.io/docs/apps/configuration/
- https://developers.home-assistant.io/docs/api/supervisor/endpoints/
