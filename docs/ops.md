# Operations

## Pods (erp namespace)

```bash
kubectl get pods -n erp
```

Expected pods: `erpnext-gunicorn`, `erpnext-nginx`, `erpnext-scheduler`, `erpnext-socketio`, `erpnext-worker-d`, `erpnext-worker-l`, `erpnext-worker-s`, `erpnext-mariadb-sts-0`, `erpnext-valkey-cache`, `erpnext-valkey-queue`.

## Rolling update deadlock fix

ERPNext uses `podAffinity` (all pods follow gunicorn to the same node) + `topologySpreadConstraints: []` to prevent rolling update deadlock on RWO PVCs.

If pods get stuck during a rolling update, check for scheduling conflicts:

```bash
kubectl describe pod -n erp <stuck-pod> | grep -A5 Events
```

## MariaDB access

```bash
kubectl exec -n erp -it erpnext-mariadb-sts-0 -- mysql -u root -p
# Password from ESO secret erpnext-mariadb-root → key mariadb-root-password
```

## Site admin password

Stored in ESO secret `erpnext-admin-secret` → key `ERPNEXT_ADMIN_PASSWORD`.

```bash
kubectl get secret -n erp erpnext-admin-secret -o jsonpath='{.data.ERPNEXT_ADMIN_PASSWORD}' | base64 -d
```

## Image tag rotation

CI bumps `minicloud-gitops/helm-values/minicloud-1/erpnext-values.yaml` → `image.tag` on every push to `main`. ArgoCD auto-syncs when the app is in sync mode.
