FROM frappe/erpnext:v16.28.0

ARG CA_CERT

USER root

RUN /home/frappe/frappe-bench/env/bin/pip install \
    "factur-x==2.0.0" \
    --no-cache-dir

RUN if [ -n "${CA_CERT}" ]; then \
        echo "${CA_CERT}" > /usr/local/share/ca-certificates/minicloud-ca.crt && \
        update-ca-certificates; \
    fi

USER frappe
