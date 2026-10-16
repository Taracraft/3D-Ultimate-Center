# Build ONLY a prepared context, never the entire Studio repository.
# The reviewed release pipeline must supply an immutable Python base digest.
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
LABEL org.opencontainers.image.title="Ultimate Slicer Server"
LABEL org.opencontainers.image.description="Source preflight; runtime installation is not yet approved"
LABEL org.opencontainers.image.licenses="SEE-LICENSES-IN-IMAGE"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV CURA_ENGINE_SEARCH_PATH=/engine/curaengine/resources/definitions:/engine/curaengine/resources/extruders
# Runtime libraries for Linux/amd64 Bambu, Prusa and Cura headless engines.
# Shared GTK/wx libraries satisfy CLI linkage; no desktop application is installed.
# Record resolved versions; publication still requires a reviewed package lock/SBOM.
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-core \
    fonts-noto-cjk \
    jq \
    libarcus5 \
    libboost-chrono1.83.0t64 \
    libboost-filesystem1.83.0 \
    libboost-log1.83.0 \
    libboost-nowide1.83.0 \
    libboost-thread1.83.0 \
    libglew2.2 \
    libgomp1 \
    libimath-3-1-29t64 \
    libmpfr6 \
    libnlopt0 \
    libopenvdb10.0t64 \
    libpolyclipping22 \
    libprotobuf32t64 \
    libqhull-r8.0 \
    libqhullcpp8.0 \
    libtbb12 \
    libtbbmalloc2 \
    libwxbase3.2-1t64 \
    libwxgtk-gl3.2-1t64 \
    libwxgtk-webview3.2-1t64 \
    libwxgtk3.2-1t64 \
    libcairo2 \
    libdbus-1-3 \
    libfontconfig1 \
    libgdk-pixbuf-2.0-0 \
    libgl1 \
    libglib2.0-0t64 \
    libgstreamer-plugins-base1.0-0 \
    libgstreamer1.0-0 \
    libgtk-3-0t64 \
    libjavascriptcoregtk-4.1-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libwayland-client0 \
    libwayland-server0 \
    libwebkit2gtk-4.1-0 \
    libx11-6 \
    && mkdir -p /usr/share/ultimate-slicer-server \
    && dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\n' \
       > /usr/share/ultimate-slicer-server/debian-packages.tsv \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/ultimate-slicer-server
COPY --chown=65532:65532 payload/ ./payload/
COPY --chown=65532:65532 context-manifest.json verify_profile_sources.py PROFILE_SOURCE_BUNDLE.json target_image_sbom.py TARGET_IMAGE_REFERENCE.json container_check.py container_runtime.py container_probe.py container_service.py container_engines.py LICENSE THIRD_PARTY_NOTICES.md PAYLOAD_PROVENANCE.json ./
COPY --chown=65532:65532 licenses/ ./licenses/
# Fixed FHS paths for reviewed Prusa/Cura archives; no engine executed here.
RUN python3 container_engines.py prepare-image \
    && python3 container_engines.py verify-image \
    && chmod 0555 payload/progress-pipe-reader.py
USER 65532:65532
ENTRYPOINT ["python3", "/opt/ultimate-slicer-server/container_check.py"]
CMD ["check"]
