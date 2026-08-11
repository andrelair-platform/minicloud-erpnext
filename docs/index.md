# minicloud-erpnext

Custom ERPNext image for the **ktayl solution** insurance information system.

## What this image adds

| Layer | Detail |
|---|---|
| Base | `frappe/erpnext:v16.28.0` |
| Added app | `erpnext_facturx` — Frappe app installed via `pip install -e` |
| Added libs | `factur-x`, `pypdf` |
| Hook | `on_submit` on `Sales Invoice` → generates Factur-X Minimum CII XML |

## ERPNext configuration (ERP-1)

Deployed at `https://erp.devandre.sbs` in the `erp` namespace, site name `erp.devandre.sbs`.

| Config area | Detail |
|---|---|
| Chart of Accounts | French PCG 2025 — 845 accounts (`fr_plan2025_comptable_general_avec_code`) |
| Company defaults | Receivable → 4111, Payable → 4011, Bank → 5121 |
| Tax templates | TVA 20%/10%/5.5% + TSCA 9%/13%/33% (insurance = TSCA not TVA) |
| CRM pipeline | 8 stages: Prospection → Perdue |
| LOB hierarchy | Produits d'Assurance → IARD (8 sub-groups) + Vie & Prévoyance (3 sub-groups) |
| Fiscal year | 2026 |

## Infrastructure

| Component | Detail |
|---|---|
| MariaDB | 10.6, Longhorn 8 Gi, pinned to `set-hog` |
| Valkey cache | Redis-fork, in-memory cache for Frappe |
| Valkey queue | Redis-fork, background job queue for Frappe workers |
| Persistent storage | Longhorn 8 Gi RWO on `fast-skunk` (sites volume) |

## CI pipeline

Follows the `minicloud-open-webui` pattern:

1. Trivy vulnerability scan
2. `docker build` with `--build-arg CA_CERT` (minicloud CA injected at build time)
3. Cosign image signing
4. SBOM generation
5. GPG-signed GitOps bump to `minicloud-gitops` (`erpnext-values.yaml` image tag)
