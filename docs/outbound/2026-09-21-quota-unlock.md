# Quota unlock — Omar runs these, agents never do

The live Travel Buddy layer is gated by `QuotaLedger.can_spend()`. The durable dict `sarjy-quota` was seeded at `spent=120` (the pessimistic default). Remaining is `120 - 120 - 40 = 0`, so every visa answer is map/CSV fallback. True spend from committed fetches is **3** (`data/README.md`).

Agents never fire a live RapidAPI request and never write this dict. Run these yourself.

## 1. Confirm the key is on Modal

In the Modal dashboard: the `sarjy` app's secret / env must contain `RAPIDAPI_KEY`. The host defaults to `visa-requirement.p.rapidapi.com` if `RAPIDAPI_HOST` is unset.

A missing key logs `travel_buddy: RAPIDAPI_KEY not configured -- live layer skipped (V9)` and never spends, even after unlock.

## 2. Unlock the ledger

`skip_if_exists=True` on seed means changing `QUOTA_SPENT_SEED` alone does **nothing** once the dict exists. Overwrite `spent` explicitly:

```bash
cd backend && uv run python -c "import modal; modal.Dict.from_name('sarjy-quota').put('spent', 3); print('spent', modal.Dict.from_name('sarjy-quota').get('spent'))"
```

Expect `spent 3`. Then remaining is `120 - 3 - 40 = 77`.

## 3. Make a recreated dict seed honestly

Set `QUOTA_SPENT_SEED=3` on the Modal app env (dashboard, or `modal secret`). If the dict is ever deleted and recreated, it must not seed 120 again.

## 4. Warm the demo pairs (after deploy)

`data/cache/` is empty and gitignored. Each live miss writes one file inside the running container. Ask these once on the deployed URL (or run `fetch_reference` locally — that spends against the **same** ledger, so do it after unlock, and it writes *reference* files, not the runtime cache):

| Passport | Destination | Why |
|---|---|---|
| EG | DE | The live-run pair that fell to CSV |
| SA | JP | Already have the committed body; a live hit still warms the container cache |
| SA | DE | Gulf origin, same destination as the demo |
| AE | GB | Second Gulf passport |
| EG | US | Second origin, a visa-required contrast |

Five requests. After that, those pairs are layer=`cache` and cost zero.

Local equivalent (spends 5, writes raw bodies you can inspect — **does not** populate the Modal container cache):

```bash
cd backend && uv run python -m scripts.fetch_reference batch \
  --pairs EG:DE,SA:JP,SA:DE,AE:GB,EG:US \
  --spend 5 \
  --out-dir /tmp/sarjy-visa-warm
```

## 5. Confirm it took

The header chip should read `visa quota · 72 left` (or similar, 77 minus however many warm hits ran) rather than `visa quota · reserve only`. A sourced visa sentence should name a duration when the live body has one, not "visa required" from the CSV.
