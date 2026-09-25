# worker/

Dockerfiles only. Each builds an RQ worker image with a different set of model
dependencies:

| Dockerfile | Base | Queues it is wired to |
|---|---|---|
| `Dockerfile.cfi-roi` | `python:3.12-slim` (CPU) | `cfi-roi`, `default` |
| `Dockerfile.inference` | `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime` | `default`, `cfi-roi`, `cfi-keypoints`, `cfi-odfd`, `cfi-quality` |
| `Dockerfile.cfi-amd` | `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime` | `cfi-amd` |
| `Dockerfile.layersegmentation` | `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime` | `layer-segmentation` |

**How to run them: `deploy/compose.workers.yaml`.** One file, configured from
`deploy/.env`, for workers on the platform host and on a separate GPU box alike.
See *Workers* in the
[production guide](https://eyened.github.io/eyened-platform/deployment/production/).

To rebuild one image:

```bash
cd deploy
docker compose -f compose.workers.yaml --profile gpu-layer-segmentation \
  build worker-layersegmentation
```

The notebook one-shot helpers (`eyened_orm.inference.docker_runner`) resolve
their image from that same file. Set `EYENED_DEPLOY_DIR` if your `deploy/`
directory is not a sibling of this one.
