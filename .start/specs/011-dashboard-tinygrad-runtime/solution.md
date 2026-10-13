# Solution: Dashboard Tinygrad Runtime

## Approach

`get_placement_previews` already tries every MLX sharding and runtime combination. Add Tinygrad with Pipeline for each node count. The memory delta for that preview uses `model_placement_bytes`, the same budget placement enforces.

The dashboard's runtime union becomes `MlxRing | MlxJaccl | Tinygrad`. State parsing keeps `TinygradInstance` beside the two MLX tags. A cluster whose reported backends contain a Tinygrad or Windows identity and no `MLX` backend selects Tinygrad and Pipeline until the person clicks a runtime button.

## Files

- `src/exo/api/main.py` — Tinygrad Pipeline previews.
- `dashboard/src/lib/stores/app.svelte.ts` — preview type, instance tag, node backends.
- `dashboard/src/routes/+page.svelte` — runtime control, default, launch, and instance label.
- `dashboard/src/lib/components/ModelCard.svelte` — runtime badge.
- `dashboard/src/lib/components/ChatSidebar.svelte` — instance label.
- `src/exo/shared/types/worker/instances.py` — accept backend names on the preview round-trip.
