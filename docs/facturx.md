# Factur-X on_submit Hook

## What it does

When a Sales Invoice is submitted in ERPNext, the `erpnext_facturx` Frappe app fires an `on_submit` hook that generates a **Factur-X Minimum** CII XML attachment and saves it to the invoice document.

## Profile

`urn:factur-x.eu:1p0:minimum` — the legally mandatory minimum for French B2B e-invoicing (EN 16931 subset).

## Validation

13/13 assertions pass on the generated XML:

| # | Assertion |
|---|---|
| 1 | Root element: `CrossIndustryInvoice` in namespace `urn:un:unece:uncefact:data:standard:CrossIndustryInvoiceType:100` |
| 2 | `ExchangedDocumentContext/GuidelineSpecifiedDocumentContextParameter/ID` = minimum profile URN |
| 3 | `ExchangedDocument/ID` present (invoice number) |
| 4 | `ExchangedDocument/TypeCode` = `380` (commercial invoice) |
| 5 | `ExchangedDocument/IssueDateTime/DateTimeString` present |
| 6 | `IssueDateTime/DateTimeString[@format="102"]` = `YYYYMMDD` |
| 7 | Seller `SpecifiedTaxRegistration/ID[@schemeID="FC"]` (SIRET) |
| 8 | Seller `SpecifiedTaxRegistration/ID[@schemeID="VA"]` (TVA/SIRET prefix) |
| 9 | Buyer `SpecifiedTaxRegistration/ID[@schemeID="FC"]` present |
| 10 | `SpecifiedTradeSettlementHeaderMonetarySummation/TaxBasisTotalAmount` present |
| 11 | `TaxTotalAmount[@currencyID="EUR"]` present |
| 12 | `GrandTotalAmount` present |
| 13 | `DuePayableAmount` present |

## Post-deploy step (required once)

After the first deploy (or disaster recovery restore), `erpnext_facturx` must be registered in the Frappe site:

```bash
kubectl exec -n erp -it \
  $(kubectl get pod -n erp -l app.kubernetes.io/name=erpnext-gunicorn -o name | head -1) \
  -- bash -c "cd /home/frappe/frappe-bench && bench --site erp.devandre.sbs install-app erpnext_facturx"
```

Without this step, the `on_submit` hook will not fire even though the app is pip-installed in the image.

## Known gotchas

| Gotcha | Fix |
|---|---|
| `frappe.init()` CWD error (`FileNotFoundError: logs/database.log`) | Run scripts from `sites/` not bench root |
| Redis stale cache after COA replacement | `frappe.cache.flushall()` in migration script |
| Hook does not fire even though app is pip-installed | Run `bench --site <site> install-app erpnext_facturx` — pip ≠ Frappe site registration |
