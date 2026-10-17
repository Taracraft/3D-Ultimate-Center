# Supervisor runtime source integration

The source includes the explicitly selected Supervisor app runtime and the
source-bound app context builder. These components are not a published image,
an installed app, or a release binding. The engine catalogue remains pending
until actual public archives and the corresponding source/license review exist.

## Runtime separation

Compose keeps its existing network-none/PID-visibility validation unchanged.
The app selects a separate explicit policy; it does not fall back to Compose
when its policy fails. Linux/amd64 and Landlock ABI 6 are required. Root setup
prepares only app-owned data and validated TLS files, then the manager/API/worker
run as uid/gid 65532 with all capability sets empty. Default-deny seccomp is
installed and inherited. The worker adds filesystem/signal/abstract-Unix
confinement and denies socket operations and alternative IPC. It receives no
Supervisor token or API secret. Missing kernel support blocks startup.

The short initial root setup is not capability-free. The separately tested
context used bounded setup capabilities and no host/Docker API or host network.
A source check or a few negative probes are not a complete security audit.

## Controlled shutdown

Graceful SIGTERM goes to each owned API/worker process. The worker must control
its own readiness handshake and descendants; group SIGTERM could kill an
unready dispatch child and create an unnecessary recovery latch. Timeout still
uses process-group SIGKILL. No recovery file is silently deleted on restart.

## Build chain

Use the existing prepared source context and an independently pinned complete
three-engine distribution with prepare_runtime_context.py. The resulting
runtime context is the only input to prepare_supervisor_context.py. Its four
required source-manifest/Dockerfile/catalog/Compose SHA-256 pins stay mandatory.
The app builder verifies the runtime before and after copying, refuses existing
outputs, and independently verifies generated app files. No engine is executed.

The app metadata uses manual_only boot, an explicit administrator API secret,
a read-only standard ssl mount, certificate validation and no default host port.
The declared image is a future publication target until a matching public image
and reviewed HA release reference actually exist. Do not register a private
build context as a finished release.

## Verification boundaries

The previously tested private candidate completed four empty start/stop cycles
with TLS and expected public/unauthenticated/authenticated HTTP responses.
Synthetic policy tests verified kernel restrictions and legitimate work, not
real slicing. Canonical-source and package regressions are separately required
for this integration; their final checkpoint records the actual outcomes.
External UI, iPhone, pilot and installation checks are not release gates and
remain not_run unless actually performed. No live migration or printer action
is implied.

Primary specifications consulted: Home Assistant app configuration
(https://contributors.home-assistant.io/apps/reference/configuration/) and
Linux Landlock userspace API (https://docs.kernel.org/userspace-api/landlock.html).
[Setup controller](SUPERVISOR_APP_SETUP.md) · [Runtime contexts](RUNTIME_CONTEXT.md)
