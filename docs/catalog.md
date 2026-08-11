# Backstage Catalog Design

## Why certain relation sections are empty

The Backstage component overview for `minicloud-erpnext` intentionally leaves three sections empty. This is correct — not missing configuration.

### Depends on components — empty

This section shows other **Component** kind entities (microservices) that ERPNext calls at runtime. ERPNext is a standalone application: it does not call `platform-demo`, `minicloud-plane`, or any other service registered in the catalog. The infrastructure dependencies (MariaDB, Valkey) appear in **Depends on resources** because they are `Resource` kind entities.

### Has subcomponents — empty

This populates when another entity declares `spec.subcomponentOf: component:default/minicloud-erpnext`. ERPNext is monolithic — gunicorn, nginx, scheduler, socketio, and workers are one Helm release, one deployed unit. No sub-piece is independently deployed with its own catalog entry.

### Consumed APIs — empty

This shows APIs where ERPNext declares `spec.consumesApis` pointing to a registered Backstage `API` entity. ERPNext provides the Frappe REST API (shown in **Provided APIs**) but does not call any catalog-registered API at runtime.

---

## When to update these sections

| Section | Add an entry when… |
|---|---|
| Depends on components | ERPNext is wired to call another catalog Component at runtime (e.g. a claims service, a policy-admin microservice) |
| Has subcomponents | `erpnext_dsn` or `erpnext_facturx` is split into a standalone deployed service with its own catalog entry |
| Consumed APIs | A Backstage `API` entity is registered for GoCardless, Net-Entreprises, or another runtime integration, and ERPNext consumes it |

Do **not** add phantom entries to fill these sections. They drive Backstage's dependency graph and impact analysis — incorrect entries mislead incident responders.

---

## What is correctly populated

| Section | Content |
|---|---|
| Depends on resources | `erpnext-mariadb`, `erpnext-valkey-cache`, `erpnext-valkey-queue` |
| Provided APIs | `erpnext-rest-api` (OpenAPI — Frappe REST + RPC, Factur-X endpoint) |
| Kubernetes tab | All pods with `app.kubernetes.io/app=frappe` in `erp` namespace |
| TechDocs | This documentation (Overview, Factur-X, Operations, Catalog design) |
