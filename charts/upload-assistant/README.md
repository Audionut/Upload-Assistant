# upload-assistant (Web UI)

Helm chart for running Upload-Assistant's Web UI (Docker GUI) on Kubernetes.

## Prerequisites

- Kubernetes cluster
- Helm 3
- A valid Upload-Assistant `config.py` (see https://github.com/Audionut/Upload-Assistant/wiki/Configuration)

## TL;DR

1. Pick a namespace (example: `upload-assistant`):

   ```bash
   kubectl create namespace upload-assistant --dry-run=client -o yaml | kubectl apply -f -
   ```

2. Create a Secret containing your `config.py` (recommended):

   ```bash
   kubectl -n upload-assistant create secret generic upload-assistant-config \
     --from-file=config.py=/path/to/config.py
   ```

3. Install/upgrade the chart:

   ```bash
   helm upgrade --install upload-assistant ./charts/upload-assistant \
     --namespace upload-assistant --create-namespace \
     -f my-values.yaml
   ```

## Installing the chart

From the repo root:

```bash
helm upgrade --install upload-assistant ./charts/upload-assistant \
  --namespace upload-assistant --create-namespace \
  -f my-values.yaml
```

## Accessing the Web UI

- `ClusterIP` (default): `kubectl -n upload-assistant port-forward deploy/upload-assistant 5000:5000`
- `LoadBalancer`: `kubectl -n upload-assistant get svc upload-assistant -w`
- `Ingress`: set `ingress.enabled=true` and configure `ingress.hosts`

## Uninstalling the chart

```bash
helm uninstall upload-assistant --namespace upload-assistant
```

## Configuration

All values (and defaults) are documented in `values.yaml`. A fuller working example is also available at the repo root: `upload-assistant-values.yaml`.

### Providing `config.py`

Upload-Assistant reads configuration from `/Upload-Assistant/data/config.py`.

Recommended approach (default):

- Create a Secret named `upload-assistant-config` containing a `config.py` key.
- Keep `config.enabled=true` and `config.existingSecret=upload-assistant-config`.
  - The Secret/ConfigMap must exist in the same namespace as the Helm release.

Alternatives:

- Provide an existing ConfigMap via `config.existingConfigMap`
- Inline config (chart-managed Secret/ConfigMap) via `config.kind` + `config.configPy` (convenient for quick testing; avoid committing real credentials)

#### Inline config details

To have the chart create the Secret/ConfigMap for you:

- Set `config.existingSecret=""` and `config.existingConfigMap=""`
- Set `config.kind` to `secret` or `configMap`
- Put the contents of your `config.py` file into `config.configPy` (use a YAML block scalar like `|-` and keep indentation)
- If you don’t need `config.py` to be writable, set `config.copyToVolume=false` to mount it read-only at `config.mountPath`

The chart creates a resource named `<release fullname>-config` containing the key `config.key` (defaults to `config.py`).

Example:

```yaml
config:
  enabled: true
  existingSecret: ""
  existingConfigMap: ""
  kind: secret # secret | configMap
  key: config.py
  copyToVolume: true
  overwrite: true
  configPy: |-
    config = {
        "DEFAULT": {
            "tmdb_api": "<your-tmdb-api-key>",
        }
    }
```

If `config.copyToVolume=true`, the chart copies the Secret/ConfigMap file into the writable `persistence.uaData` volume on startup so it can be persisted/edited. Use `config.overwrite` to control whether it is replaced on every start.

### Persistence

- `persistence.uaData`: backs `/Upload-Assistant/data` (must be writable; this is where `config.py` lives)
- `persistence.tmp`: backs `/Upload-Assistant/tmp` (recommended)
- `persistence.files`: optional mount (often NFS) so the UI can browse your downloads/media (typical mountPath: `/data`)
- `persistence.torrentStorage`: optional mount for torrent client state (e.g. qBittorrent `BT_backup`) used for torrent re-use

If you use the Web UI file browser, set `persistence.files.mountPath` to match the `local_path` you configure in `config.py`.

### Common values example

```yaml
# Run as the same user/group as your torrent client so UA can read/write the same files.
podSecurityContext:
  fsGroup: 1000
securityContext:
  runAsUser: 1000
  runAsGroup: 1000

extraEnv:
  - name: TZ
    value: America/Denver

config:
  enabled: true
  existingSecret: upload-assistant-config
  copyToVolume: true
  overwrite: true

persistence:
  files:
    enabled: true
    type: nfs
    mountPath: /data
    nfs:
      server: <nfs-server-ip>
      path: /path/to/share

  uaData:
    enabled: true
    type: pvc
    storageClassName: <your-storage-class>
    size: 1Gi

  tmp:
    enabled: true
    type: emptyDir

service:
  type: ClusterIP # or LoadBalancer

# Optional ingress
ingress:
  enabled: false
  className: ""
  annotations: {}
  hosts:
    - host: upload.example.local
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls: []
```

## Parameters

| Key | Description | Default |
| --- | --- | --- |
| `image.repository` | Image repository | `ghcr.io/audionut/upload-assistant` |
| `image.tag` | Image tag (defaults to chart `appVersion`) | `""` |
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `5000` |
| `ingress.enabled` | Enable ingress | `false` |
| `config.enabled` | Enable config management | `true` |
| `config.existingSecret` | Existing Secret name containing `config.key` | `upload-assistant-config` |
| `config.existingConfigMap` | Existing ConfigMap name containing `config.key` | `""` |
| `config.kind` | Create a `secret` or `configMap` when not using `existingSecret`/`existingConfigMap` | `secret` |
| `config.key` | Key name in the Secret/ConfigMap | `config.py` |
| `config.mountPath` | Mount/copy destination path | `/Upload-Assistant/data/config.py` |
| `config.copyToVolume` | Copy config into `persistence.uaData` (writable) | `true` |
| `config.overwrite` | Overwrite destination on every start | `true` |
| `config.configPy` | Inline `config.py` contents (used when creating Secret/ConfigMap) | `""` |
| `persistence.uaData.enabled` | Enable `/Upload-Assistant/data` volume | `true` |
| `persistence.uaData.type` | Storage type for `/Upload-Assistant/data` | `pvc` |
| `persistence.tmp.enabled` | Enable `/Upload-Assistant/tmp` volume | `true` |
| `persistence.tmp.type` | Storage type for `/Upload-Assistant/tmp` | `emptyDir` |
| `persistence.files.enabled` | Enable optional files volume (UI browser) | `false` |
| `persistence.files.type` | Storage type for files volume | `nfs` |
| `extraEnv` | Extra environment variables | `[{name: ENABLE_WEB_UI, value: "true"}]` |
