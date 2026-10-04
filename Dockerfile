FROM frappe/erpnext:v16.28.0

ARG CA_CERT

USER root

# ── Security remediation of base-image (frappe/erpnext:v16.28.0) CRITICAL CVEs ──────────────────
# A fresh Trivy scan surfaced CRITICALs that ship in the base image (they pre-date HR-12; the running
# image carries the same). We SOLVE them here rather than suppress — patch what's patchable, delete
# the build-only artifacts that aren't needed at production runtime (Frappe serves pre-built assets):
#   (a) OS: chromium* (headless PDF renderer) + libgnutls30 → the fixed Debian 12 releases;
#   (b) Python: GitPython + PyJWT in BOTH the frappe venv AND the base /usr/local python;
#   (c) node build-tooling: esbuild platform binaries (the Go-stdlib CVEs; the arm64 one can't even
#       run on amd64), loader-utils, shell-quote + its only consumer launch-editor — all build/dev-time
#       only; the realtime/socketio runtime does NOT require them.
# The one residual (node-tar bundled inside the npm CLI, a build-time DoS not in the runtime path) is
# unpatchable without a node bump the v16.28.0 base can't take → a single justified .trivyignore entry.
RUN apt-get update \
 && apt-get install -y --only-upgrade \
      $(dpkg-query -W -f='${Package}\n' 'chromium*' 2>/dev/null | tr '\n' ' ') \
      libgnutls30 \
 && rm -rf /var/lib/apt/lists/*
RUN /usr/local/bin/pip install --no-cache-dir --upgrade "GitPython>=3.1.59" \
 && cd /home/frappe/frappe-bench/apps \
 && find . -type d -name 'esbuild-*' -prune -exec rm -rf {} + \
 && find . -type d \( -name loader-utils -o -name shell-quote -o -name launch-editor \) -prune -exec rm -rf {} +

RUN /home/frappe/frappe-bench/env/bin/pip install \
    "factur-x==2.0.0" \
    "requests>=2.31.0" \
    "stripe>=7.0.0" \
    "nats-py>=2.6.0" \
    "GitPython>=3.1.59" \
    "PyJWT>=2.14.0" \
    --no-cache-dir

# Bake erpnext_facturx Frappe app into the image
COPY erpnext_facturx/ /home/frappe/frappe-bench/apps/erpnext_facturx/
RUN /home/frappe/frappe-bench/env/bin/pip install -e \
    /home/frappe/frappe-bench/apps/erpnext_facturx --no-cache-dir

# Bake erpnext_dsn Frappe app into the image
COPY erpnext_dsn/ /home/frappe/frappe-bench/apps/erpnext_dsn/
RUN /home/frappe/frappe-bench/env/bin/pip install -e \
    /home/frappe/frappe-bench/apps/erpnext_dsn --no-cache-dir

# Bake erpnext_sepa Frappe app into the image
COPY erpnext_sepa/ /home/frappe/frappe-bench/apps/erpnext_sepa/
RUN /home/frappe/frappe-bench/env/bin/pip install -e \
    /home/frappe/frappe-bench/apps/erpnext_sepa --no-cache-dir

# Bake erpnext_hr_lifecycle Frappe app into the image (J/M/L event emission — HR#8 ↔ ktayl-iam#17 seam)
COPY erpnext_hr_lifecycle/ /home/frappe/frappe-bench/apps/erpnext_hr_lifecycle/
RUN /home/frappe/frappe-bench/env/bin/pip install -e \
    /home/frappe/frappe-bench/apps/erpnext_hr_lifecycle --no-cache-dir

# Install hrms (HR & Payroll module for frappe v16 — provides Salary Slip, Payroll Entry, etc.)
# version-16 branch is the stable series for frappe/erpnext v16.x.
RUN git clone --depth 1 --branch version-16 \
        https://github.com/frappe/hrms.git \
        /home/frappe/frappe-bench/apps/hrms && \
    /home/frappe/frappe-bench/env/bin/pip install -e \
        /home/frappe/frappe-bench/apps/hrms --no-cache-dir

RUN if [ -n "${CA_CERT}" ]; then \
        echo "${CA_CERT}" > /usr/local/share/ca-certificates/minicloud-ca.crt && \
        update-ca-certificates; \
    fi

USER frappe
