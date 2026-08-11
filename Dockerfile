FROM frappe/erpnext:v16.28.0

ARG CA_CERT

USER root

RUN /home/frappe/frappe-bench/env/bin/pip install \
    "factur-x==2.0.0" \
    "requests>=2.31.0" \
    --no-cache-dir

# Bake erpnext_facturx Frappe app into the image
COPY erpnext_facturx/ /home/frappe/frappe-bench/apps/erpnext_facturx/
RUN /home/frappe/frappe-bench/env/bin/pip install -e \
    /home/frappe/frappe-bench/apps/erpnext_facturx --no-cache-dir

# Bake erpnext_dsn Frappe app into the image
COPY erpnext_dsn/ /home/frappe/frappe-bench/apps/erpnext_dsn/
RUN /home/frappe/frappe-bench/env/bin/pip install -e \
    /home/frappe/frappe-bench/apps/erpnext_dsn --no-cache-dir

RUN if [ -n "${CA_CERT}" ]; then \
        echo "${CA_CERT}" > /usr/local/share/ca-certificates/minicloud-ca.crt && \
        update-ca-certificates; \
    fi

USER frappe
