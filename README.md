# Hydrosat Azure Challenge 🚀

_Build a secure, daily‑partitioned geospatial pipeline on Azure._

## Quick start

```bash
./deploy.sh               # takes ~15 min
# open dagster UI
```

## Folder guide

| Path       | Purpose                                      |
| ---------- | -------------------------------------------- |
| terraform/ | All Azure resources coded in HCL             |
| dagster/   | Dagster project, Dockerfile, code            |
| helm/      | Helm overrides for Dagster chart             |
| deploy.sh  | One‑shot wrapper – Terraform → Docker → Helm |

## Inputs

Upload once:

```bash
az storage blob upload-batch -s inputs/ -d inputs --account-name <storage>
```

* `bbox.json` – bounding rectangle `[xmin,ymin,xmax,ymax]`
* `fields.geojson` – polygons you drew via [https://geojson.io](https://geojson.io)

## Common commands

| Action           | Command                             |
| ---------------- | ----------------------------------- |
| See cluster pods | `kubectl get pods -n dagster`       |
| Tail a run       | Dagit ▸ Runs ▸ click run            |
| Tidy all         | `cd terraform && terraform destroy` |

## AI disclosure

Text, code, and the architecture diagram were drafted with **OpenAI o3** (ChatGPT) and reviewed by a human.

---

Enjoy ☀️ – PRs welcome!