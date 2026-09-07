# worker/

Dockerfiles only. Each builds an RQ worker image with a different set of model
dependencies:

| Dockerfile | Base | Queues it is wired to |
|---|---|---|
| `Dockerfile.cfi-roi` | `python:3.12-slim` (CPU) | `cfi-roi`, `default` |
| `Dockerfile.inference` | `pytorch:2.7.1-cuda12.8` | `default`, `cfi-roi`, `cfi-keypoints`, `cfi-odfd`, `cfi-quality` |
| `Dockerfile.cfi-amd` | `pytorch:2.7.1-cuda12.8` | `cfi-amd` |
| `Dockerfile.layersegmentation` | `pytorch:2.7.1-cuda12.8` | `layer-segmentation` |

**How to run them: `deploy/compose.workers.yaml`.** One file, for workers on
the platform host and on a separate GPU box alike. There is no `.env` here any
more — compose reads `deploy/.env` from the compose file's own directory, so
there is one env file for both cases. See the *Workers* section of
[`deploy/README.md`](../deploy/README.md).

To rebuild one image:

```bash
cd deploy
docker compose -f compose.workers.yaml --profile gpu-layer-segmentation \
  build worker-layersegmentation
```

The notebook one-shot helpers (`eyened_orm.inference.docker_runner`) resolve
their image from that same file. Set `EYENED_DEPLOY_DIR` if your `deploy/`
directory is not a sibling of this one.
