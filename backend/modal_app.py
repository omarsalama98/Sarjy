"""Modal deployment entrypoint.

Two settings are load-bearing and easy to miss:

  timeout=        bounds the WebSocket lifetime. The 300 s default kills a
                  ten-minute conversation at five minutes.
  min_containers= keeps one container warm so the reviewer never waits on a
                  cold start. Costs ~$14/mo at 24/7; flip it on for the demo
                  window instead if that matters.
"""

import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_pyproject("pyproject.toml")
    .add_local_python_source("app")
)

app = modal.App("sarjy", image=image)


@app.function(
    timeout=3600,          # WebSocket lifetime. Do not leave at the default.
    min_containers=1,      # No cold start in front of the reviewer.
    secrets=[modal.Secret.from_name("sarjy-secrets")],
)
@modal.asgi_app()
def fastapi_app():
    from app.main import app as fastapi

    return fastapi
