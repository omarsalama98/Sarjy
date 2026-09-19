"""Modal deployment entrypoint.

Four settings here are load-bearing. Three of them are easy to miss and one of
them is the single most likely way this app shape breaks in front of a reviewer.

  @modal.concurrent   Modal treats ONE WEBSOCKET AS ONE INPUT. Without this,
                      every concurrent connection gets its own container — and
                      `min_containers=1` does not prevent that, because it is a
                      floor, not a cap. Two reviewers on the URL at once would
                      be two containers with two separate in-memory states.
                      Verified in Modal's own WebSocket launch post.

  timeout=            Bounds the WebSocket lifetime. Modal does NOT document
                      this directly — see the note below. The 300 s default
                      would cut a ten-minute conversation at five minutes.

  min_containers=     A floor, not a cap. Keeps one container warm so the
                      reviewer never waits on a cold start.

  routing_region=     Where requests ENTER Modal's network. Distinct from
                      `region=`, which constrains where the container runs.
                      NOT A PARAMETER IN THE INSTALLED CLIENT (1.4.2) — it
                      arrived later; `pip install -U modal` for 1.5.5. Fixed
                      per Function once deployed, so a change means a new
                      Function and therefore A NEW URL. That only matters
                      once the URL has been shared. Default us-east; there
                      is no Middle East routing region.

## On the timeout, honestly

Modal documents no maximum WebSocket duration and no sentence saying `timeout=`
governs one. The inference chains two documented facts:

  1. "WebSockets on Modal maintain a single function call per connection."
  2. "The timeout duration is a measure of a Function's execution time."

One connection = one call = one execution, so `timeout` bounds it. Modal's own
reference voice app (QuiLLMan) sets `timeout=600` on its WebSocket functions,
which is consistent.

Separately, Modal documents a 150 s HTTP request timeout and never says whether
it survives a WebSocket upgrade. Evidence suggests it does not — the documented
workaround is a 303 redirect, impossible for a WebSocket — but that is
circumstantial. **Hold an idle connection past 150 s before building on this.**
"""

import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_pyproject("pyproject.toml")
    .add_local_python_source("app")
)

app = modal.App("sarjy", image=image)


@app.function(
    timeout=30 * 60,       # WebSocket lifetime. Never leave at the 300 s default.
    min_containers=1,      # Floor, not a cap. No cold start in front of the reviewer.
    max_containers=2,      # The actual cap.
    scaledown_window=300,  # Default is 60 s; too eager for a conversational app.
    secrets=[modal.Secret.from_name("sarjy-secrets")],
    # routing_region="eu-west",  # Needs modal >= 1.5.5. Fixed per Function once deployed.
)
@modal.concurrent(max_inputs=8, target_inputs=4)
@modal.asgi_app()
def fastapi_app():
    from app.main import app as fastapi

    return fastapi
