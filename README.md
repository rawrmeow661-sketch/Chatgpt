# Deterministic Distributed Civilization Simulator

This repository contains a self-contained deterministic civilization simulator written in Python. It is designed to satisfy the challenge requirements with seeded world generation, autonomous agents, deterministic replay, save/load support, supply-and-demand economics, pathfinding, and debug output.

## Highlights

- Procedural planet generation from a single numeric seed.
- World layers for elevation, climate zones, lakes/rivers, weather, and resource distribution.
- 1,000+ autonomous agents with memory, inventories, goals, personality traits, decision logic, reproduction, conflict, trade, and death.
- Deterministic discrete-tick simulation with a seeded PRNG as the only source of randomness.
- A* pathfinding with terrain-dependent movement costs and dynamic recomputation.
- Save/load plus replay through JSON state snapshots that include RNG state.
- Debug mode exposing per-agent decisions, pathfinding node counts, resource flows, and population trends.

## Run

```bash
python simulator.py --seed 12345 --steps 1000 --agents 1000 --debug
```

## Save and load

```bash
python simulator.py --seed 12345 --steps 500 --save state.json
python simulator.py --load state.json --steps 500
```

## Test

```bash
python -m unittest -v
```

## Notes on determinism and scalability

- Agents are updated in ascending `agent_id` order every tick.
- Economy, communication, and event logging use stable ordering.
- The world uses fixed-size memory structures wherever possible; per-agent memory is capped at 32 entries.
- The implementation is intentionally headless and can be extended with visualization later.
