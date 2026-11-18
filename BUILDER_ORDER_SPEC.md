# Order-invariant game building and plan comparison

For the owners of `game_builder.py` and `solver.py`. From the plan-vs-build review of 2026-10-27, task 4 (P0).

## Problem

The order of facts in a package carries no meaning. But the builder and solver use list order in three places. So when the same facts arrive in a different order, the game or plan changes. In the rewording study, every such change is counted as error. The document-level job re-extracts facts, and the model returns them in its own order, so this will happen there.

| Where | What depends on order |
|---|---|
| `game_builder.py` `_owner` (fallback branch) | A fact that names neither side gets `us` or `opponent` by alternation, so its owner depends on its position. |
| `game_builder.py` joint goals (`ours[i]` with `theirs[i]`) | Which of our actions is paired with which of theirs. |
| `solver.py` search tie-break and stable candidate sort | Which of several equally good plans comes first. The comparison only looks at the first. |

Two probes in `tests/test_peer_engines.py` (`OrderInvarianceProbes`) reproduce this with four commitment facts. Both are marked `expectedFailure`:

- **Owner probe:** swapping two facts that name neither side flips both owners, so the game and the plan both change.
- **Plan-order probe:** swapping two independent us/opponent pairs leaves the game the same, but the plan's steps come out in a different order.

On the current Qiso and example packages, shuffling facts changes nothing, because every action has an explicit owner. Sim 2-style packages do trigger it.

## Requested changes

1. **Use a canonical fact order on entry.** Sort facts by `(sourceId, quoteStart, id)` before anything else in `build_game`. This is the smallest fix that covers all three places for a pure reordering.
2. **No ownership by alternation.** When neither the subject nor a party mention decides the owner, use the source (a private or role-card source means `us`). If the source doesn't decide it either, leave the fact out of the action set and say so in `assumptions`. Don't guess.
3. **Pair joint goals by content, not position.** For example, pair actions that share a topic or a cited quote. If there's no basis for a pairing, make no joint goal.
4. **Report ties.** Return every plan whose `(worstScore, meanScore)` equals the best plan's within 1e-9, for example as `equallyGood: [plan ids]` on the first strategy. Within that set, order by action ids, not by insertion. On our side, `plan_signature` will then treat a reading as unchanged when its best plan is in the baseline's tie set. This is the "equally good alternative" bucket from plan §21.1.

## Done when

- Both `OrderInvarianceProbes` tests pass. Then remove their `expectedFailure` markers.
- Shuffling `package['facts']` (20 seeds) never changes `game_signature` or `plan_signature` on the example package, Qiso, or Sim 2.
- All existing tests still pass.

## Coming next (task 5, for discussion)

The model-built game will produce one `G` per reading. The contract change we'd like to agree on:

- `game.goals[*].usValue` becomes a per-reading column.
- `opponentReadings` carries samples of the opponent's values rather than the single `lower-joint-benefit` column.

The rule-based builder stays as the baseline it is compared against.
