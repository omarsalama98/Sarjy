---
name: modal-import-in-container
description: "import modal works inside a deployed Modal container even though modal is a dev-only pyproject dependency never installed by pip_install_from_pyproject"
metadata:
  type: project
---

Confirmed live (2026-09-20/21, Block A verification pass): `import modal` succeeds inside a
container built from `modal_app.py`'s exact image shape — `debian_slim` +
`pip_install_from_pyproject(pyproject.toml)` with no `optional_dependencies` argument — even
though `modal` lives only in `pyproject.toml`'s `dev` extra and is never installed by that call.

**Why:** Modal injects its own client library into every container it runs, regardless of what
the image's own pip dependency list says. This isn't documented as a guarantee anywhere I found;
it was verified by building a throwaway probe app (`modal.App("sarjy-modal-import-probe")`) with
the identical image-construction code and running one ephemeral function that did `import modal`
and reported the version. Output: `IMPORT_OK version=1.5.5`. The probe app was left in the
`stopped` state afterward — it does not linger, and it never touched the real `sarjy` app.

**How to apply:** `app/tools/quota.py`'s `_ModalDictStore` (the durable quota-ledger backend) is
real, not a fallback that silently never engages — the deployed app really does use `modal.Dict`
for the 120-request-ever ledger, not the in-process fallback. Any future code that assumes "modal
might not be importable in the container" should be corrected against this finding rather than
re-litigated from scratch; if Modal ever changes this behavior (e.g. a future SDK version stops
auto-injecting), re-run the same probe pattern rather than guessing.

**Reproduction, if this ever needs re-checking:** write a `modal.App` in a scratch file whose
`Image` is built the same way `modal_app.py` builds its image (same `pip_install_from_pyproject`
call, no `modal` in the installed list), add one `@app.function()` that does `import modal` and
returns something observable, and `modal run` it (not `modal deploy`) — ephemeral, tears down on
its own, and never touches the real deployed app or its quota ledger.
