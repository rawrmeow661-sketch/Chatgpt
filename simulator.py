from __future__ import annotations

import argparse
import ast
import json
import math
import heapq
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from pathlib import Path
from random import Random
from typing import Any, Dict, Iterable, List, Optional, Tuple

GOODS = ("food", "wood", "stone", "tools", "energy")
RESOURCE_TO_GOOD = {"forest": "wood", "quarry": "stone", "fertile": "food", "ore": "tools", "solar": "energy"}
PERSONALITY_KEYS = ("aggression", "cooperation", "curiosity", "diligence")


class EventType(IntEnum):
    MOVE = 1
    GATHER = 2
    BUILD = 3
    TRADE = 4
    ATTACK = 5
    RETREAT = 6
    BIRTH = 7
    DEATH = 8
    SHARE = 9


@dataclass
class MemoryEntry:
    event_type: int
    location: Tuple[int, int]
    timestamp: int
    outcome: float
    info_quality: float = 1.0


@dataclass
class Cell:
    elevation: float
    climate: int
    water: float
    river: bool
    lake: bool
    resource: str
    weather: float = 0.0
    obstacle: bool = False
    structure_owner: int = -1

    def movement_cost(self) -> float:
        cost = 1.0 + self.elevation * 2.5 + self.water * 1.5 + abs(self.weather) * 0.3
        if self.river:
            cost += 0.8
        if self.lake or self.obstacle:
            return 999999.0
        return cost


@dataclass
class Agent:
    agent_id: int
    x: int
    y: int
    energy: float
    age: int
    max_age: int
    health: float
    generation: int
    traits: Dict[str, float]
    personality: Dict[str, float]
    goals: List[str]
    inventory: Dict[str, int]
    memory: List[MemoryEntry] = field(default_factory=list)
    group_id: int = -1
    alive: bool = True
    path: List[Tuple[int, int]] = field(default_factory=list)
    path_target: Optional[Tuple[int, int]] = None
    skill: float = 1.0
    debug: Dict[str, Any] = field(default_factory=dict)

    def remember(self, event_type: EventType, location: Tuple[int, int], timestamp: int, outcome: float, info_quality: float = 1.0) -> None:
        self.memory.append(MemoryEntry(int(event_type), location, timestamp, outcome, info_quality))
        if len(self.memory) > 32:
            del self.memory[0]

    def memory_bias(self, location: Tuple[int, int]) -> float:
        score = 0.0
        for mem in self.memory:
            if mem.location == location:
                age_factor = max(0.1, 1.0 - (self.age - mem.timestamp) * 0.002)
                score += mem.outcome * mem.info_quality * age_factor
        return score


class DeterministicCivilizationSimulator:
    def __init__(self, seed: int, width: int = 48, height: int = 32, initial_agents: int = 1000, debug: bool = False):
        self.seed = seed
        self.width = width
        self.height = height
        self.initial_agents = initial_agents
        self.debug_enabled = debug
        self.rng = Random(seed)
        self.tick = 0
        self.grid: List[List[Cell]] = [[self._make_cell(x, y) for x in range(width)] for y in range(height)]
        self.market: Dict[str, float] = {g: 10.0 for g in GOODS}
        self.resource_cells: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        self.global_stock: Counter = Counter()
        self.trade_volume: Counter = Counter()
        self.population_trend: List[int] = []
        self.resource_flow: Counter = Counter()
        self.groups: Dict[int, List[int]] = defaultdict(list)
        self.events: List[Tuple[int, int, Tuple[int, int], float]] = []
        self.agent_index: Dict[int, Agent] = {}
        self.spatial_index: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        self.next_agent_id = 0
        self.agents: List[Agent] = []
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                self.resource_cells[RESOURCE_TO_GOOD[cell.resource]].append((x, y))
        self._generate_water_systems()
        self._spawn_agents(initial_agents)

    def _noise(self, *values: int) -> float:
        h = 2166136261
        for v in values:
            h = (h ^ (v + self.seed * 1315423911)) * 16777619 & 0xFFFFFFFF
        return h / 0xFFFFFFFF

    def _make_cell(self, x: int, y: int) -> Cell:
        nx = x / max(1, self.width - 1)
        ny = y / max(1, self.height - 1)
        elevation = (math.sin(nx * math.pi * 2) + math.cos(ny * math.pi * 3)) * 0.15 + self._noise(x, y, 1) * 0.7
        climate_band = int((abs(ny - 0.5) * 3 + self._noise(x, y, 2) * 2)) % 5
        water = self._noise(x, y, 3) * max(0.0, 0.8 - elevation)
        resource_roll = self._noise(x, y, 4)
        if resource_roll < 0.22:
            resource = "forest"
        elif resource_roll < 0.40:
            resource = "fertile"
        elif resource_roll < 0.56:
            resource = "quarry"
        elif resource_roll < 0.68:
            resource = "ore"
        else:
            resource = "solar"
        obstacle = elevation > 0.95
        return Cell(elevation=elevation, climate=climate_band, water=water, river=False, lake=water > 0.72, resource=resource, obstacle=obstacle)

    def _generate_water_systems(self) -> None:
        for start_x in range(0, self.width, max(3, self.width // 6)):
            x = start_x
            y = int(self._noise(start_x, 9) * (self.height - 1))
            for _ in range(self.width + self.height):
                self.grid[y][x].river = True
                best = (x, y)
                best_elev = self.grid[y][x].elevation
                for nx, ny in self.neighbors(x, y):
                    elev = self.grid[ny][nx].elevation - self.grid[ny][nx].water * 0.3
                    if elev < best_elev:
                        best_elev, best = elev, (nx, ny)
                if best == (x, y):
                    self.grid[y][x].lake = True
                    break
                x, y = best

    def _spawn_agents(self, count: int) -> None:
        for _ in range(count):
            x = int(self.rng.random() * self.width)
            y = int(self.rng.random() * self.height)
            while self.grid[y][x].lake or self.grid[y][x].obstacle:
                x = (x + 1) % self.width
                y = (y + 1) % self.height
            traits = {k: 0.5 + self.rng.random() for k in ("strength", "intelligence", "speed", "aggression", "cooperation")}
            personality = {k: self.rng.random() for k in PERSONALITY_KEYS}
            inventory = {g: 2 for g in GOODS}
            agent = Agent(
                agent_id=self.next_agent_id,
                x=x,
                y=y,
                energy=80 + self.rng.random() * 40,
                age=0,
                max_age=240 + int(self.rng.random() * 140),
                health=100.0,
                generation=0,
                traits=traits,
                personality=personality,
                goals=["survive", "prosper", "socialize"],
                inventory=inventory,
                skill=0.5 + traits["intelligence"] * 0.5,
            )
            self.agents.append(agent)
            self.agent_index[agent.agent_id] = agent
            self.next_agent_id += 1

    def neighbors(self, x: int, y: int) -> Iterable[Tuple[int, int]]:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                yield nx, ny

    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(self, start: Tuple[int, int], goal: Tuple[int, int], agent: Optional[Agent] = None) -> Tuple[List[Tuple[int, int]], int]:
        frontier = [(0.0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0.0}
        explored = 0
        while frontier:
            _, current = heapq.heappop(frontier)
            explored += 1
            if current == goal:
                break
            for nxt in self.neighbors(*current):
                cell = self.grid[nxt[1]][nxt[0]]
                move_cost = cell.movement_cost()
                if move_cost >= 999999.0:
                    continue
                bias = 0.0 if agent is None else max(-2.0, min(2.0, -agent.memory_bias(nxt) * 0.1))
                new_cost = cost_so_far[current] + move_cost + bias
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    priority = new_cost + self.heuristic(goal, nxt)
                    heapq.heappush(frontier, (priority, nxt))
                    came_from[nxt] = current
        if goal not in came_from:
            return [], explored
        path = []
        cur = goal
        while cur != start:
            path.append(cur)
            cur = came_from[cur]
        path.reverse()
        return path, explored

    def update_environment(self) -> None:
        season = (self.tick // 200) % 4
        day_phase = (self.tick % 24) / 24.0
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                weather_seed = self._noise(x, y, self.tick, season)
                cell.weather = math.sin(day_phase * math.pi * 2 + weather_seed * math.pi) + (season - 1.5) * 0.15
                if cell.river and weather_seed > 0.92:
                    cell.water = min(1.0, cell.water + 0.05)
                elif not cell.lake:
                    cell.water = max(0.0, cell.water - 0.01 + max(0.0, cell.weather) * 0.005)
                cell.obstacle = cell.elevation > 0.97 or (cell.water > 0.96 and not cell.river)

    def update_economy(self) -> None:
        total_agents = max(1, sum(1 for a in self.agents if a.alive))
        stock = Counter()
        for a in self.agents:
            if a.alive:
                stock.update(a.inventory)
        self.global_stock = stock
        for good in GOODS:
            scarcity = total_agents * 5 / max(1, stock[good])
            baseline = 10.0 + scarcity * 2.0 + self.trade_volume[good] * 0.02
            self.market[good] = round(max(1.0, min(200.0, baseline)), 4)
        self.trade_volume.clear()

    def _nearest_resource_target(self, agent: Agent, desired_good: str) -> Tuple[int, int]:
        best = (agent.x, agent.y)
        best_score = float('-inf')
        for x, y in self.resource_cells.get(desired_good, []):
            cell = self.grid[y][x]
            if cell.lake or cell.obstacle:
                continue
            score = 20 - self.heuristic((agent.x, agent.y), (x, y)) - cell.movement_cost() + agent.memory_bias((x, y))
            if score > best_score:
                best_score = score
                best = (x, y)
        return best

    def _agent_decision(self, agent: Agent) -> str:
        deficits = sorted(GOODS, key=lambda g: agent.inventory[g])
        if agent.health < 40 or agent.energy < 25:
            return "rest"
        if agent.inventory["food"] < 3:
            return "gather_food"
        if deficits[0] != "food" and agent.inventory[deficits[0]] < 3:
            return f"gather_{deficits[0]}"
        nearby = self._agents_at(agent.x, agent.y, radius=1, exclude=agent.agent_id)
        if nearby and (agent.personality["cooperation"] > 0.4 or agent.personality["aggression"] > 0.7):
            return "social"
        if agent.energy > 90 and agent.age > 30 and agent.inventory["food"] > 5:
            return "reproduce"
        if self.grid[agent.y][agent.x].structure_owner in (-1, agent.agent_id) and agent.inventory["wood"] >= 4 and agent.inventory["stone"] >= 2:
            return "build"
        return "wander"

    def _rebuild_spatial_index(self) -> None:
        self.spatial_index = defaultdict(list)
        for agent in self.agents:
            if agent.alive:
                self.spatial_index[(agent.x, agent.y)].append(agent.agent_id)

    def _agents_at(self, x: int, y: int, radius: int, exclude: Optional[int] = None) -> List[Agent]:
        found = []
        for ny in range(max(0, y - radius), min(self.height, y + radius + 1)):
            for nx in range(max(0, x - radius), min(self.width, x + radius + 1)):
                if abs(nx - x) + abs(ny - y) > radius:
                    continue
                for agent_id in self.spatial_index.get((nx, ny), []):
                    if agent_id == exclude:
                        continue
                    other = self.agent_index[agent_id]
                    if other.alive:
                        found.append(other)
        found.sort(key=lambda a: a.agent_id)
        return found

    def _move_agent_towards(self, agent: Agent, target: Tuple[int, int]) -> int:
        if agent.path_target != target or not agent.path:
            agent.path, explored = self.find_path((agent.x, agent.y), target, agent)
            agent.path_target = target
        else:
            explored = 0
        if agent.path:
            nx, ny = agent.path.pop(0)
            agent.x, agent.y = nx, ny
            agent.energy -= self.grid[ny][nx].movement_cost() * max(0.3, 1.0 - agent.traits["speed"] * 0.2)
            agent.remember(EventType.MOVE, (nx, ny), self.tick, 0.1)
            self.events.append((self.tick, int(EventType.MOVE), (nx, ny), agent.energy))
        return explored

    def _gather(self, agent: Agent, good: str) -> None:
        cell = self.grid[agent.y][agent.x]
        cell_good = RESOURCE_TO_GOOD.get(cell.resource)
        if cell_good == good:
            amount = 1 + int(agent.traits["intelligence"] + agent.traits["strength"])
            if good == "tools":
                amount = 1
            agent.inventory[good] += amount
            agent.energy -= 3.0
            self.resource_flow[good] += amount
            agent.remember(EventType.GATHER, (agent.x, agent.y), self.tick, float(amount))
            self.events.append((self.tick, int(EventType.GATHER), (agent.x, agent.y), amount))
        else:
            self._move_agent_towards(agent, self._nearest_resource_target(agent, good))

    def _trade(self, seller: Agent, buyer: Agent, good: str) -> bool:
        if seller.inventory[good] <= 2 or buyer.inventory[good] >= 5:
            return False
        price = self.market[good]
        if buyer.inventory["energy"] <= 0:
            return False
        seller.inventory[good] -= 1
        buyer.inventory[good] += 1
        buyer.inventory["energy"] -= 1
        seller.inventory["energy"] += 1
        self.trade_volume[good] += 1
        seller.remember(EventType.TRADE, (seller.x, seller.y), self.tick, price)
        buyer.remember(EventType.TRADE, (buyer.x, buyer.y), self.tick, price)
        self.events.append((self.tick, int(EventType.TRADE), (seller.x, seller.y), price))
        return True

    def _social_or_conflict(self, agent: Agent) -> None:
        nearby = self._agents_at(agent.x, agent.y, radius=1, exclude=agent.agent_id)
        for other in nearby[:3]:
            if agent.personality["aggression"] > 0.75 and agent.inventory["tools"] >= other.inventory["tools"]:
                damage = max(1.0, agent.traits["strength"] * 8 + agent.inventory["tools"] - other.traits["speed"] * 2)
                other.health -= damage
                agent.energy -= 4
                other.remember(EventType.ATTACK, (agent.x, agent.y), self.tick, -damage)
                agent.remember(EventType.ATTACK, (agent.x, agent.y), self.tick, damage)
                self.events.append((self.tick, int(EventType.ATTACK), (agent.x, agent.y), damage))
                if other.health < 25:
                    other.path = []
                    safe = self._nearest_resource_target(other, "food")
                    self._move_agent_towards(other, safe)
                    other.remember(EventType.RETREAT, (other.x, other.y), self.tick, 1.0)
                if other.health <= 0:
                    other.alive = False
                    agent.inventory["food"] += other.inventory["food"] // 2
                    self.events.append((self.tick, int(EventType.DEATH), (other.x, other.y), other.agent_id))
                break
            else:
                for mem in other.memory[-2:]:
                    degraded = max(0.2, mem.info_quality * 0.9)
                    maybe_false = mem.outcome
                    if self.rng.random() < 0.03:
                        maybe_false = -maybe_false
                    agent.memory.append(MemoryEntry(mem.event_type, mem.location, mem.timestamp, maybe_false, degraded))
                agent.group_id = min(agent.agent_id, other.agent_id)
                other.group_id = agent.group_id
                self.groups[agent.group_id].extend([agent.agent_id, other.agent_id])
                for good in GOODS:
                    if self._trade(agent, other, good) or self._trade(other, agent, good):
                        break
                self.events.append((self.tick, int(EventType.SHARE), (agent.x, agent.y), float(agent.group_id)))
                break

    def _build(self, agent: Agent) -> None:
        cell = self.grid[agent.y][agent.x]
        if cell.structure_owner == -1:
            cell.structure_owner = agent.agent_id
            agent.inventory["wood"] -= 4
            agent.inventory["stone"] -= 2
            agent.energy -= 5
            agent.remember(EventType.BUILD, (agent.x, agent.y), self.tick, 1.0)
            self.events.append((self.tick, int(EventType.BUILD), (agent.x, agent.y), agent.agent_id))

    def _reproduce(self, agent: Agent) -> None:
        mate = None
        for other in self._agents_at(agent.x, agent.y, radius=1, exclude=agent.agent_id):
            if other.age > 30 and other.inventory["food"] > 5 and other.energy > 70:
                mate = other
                break
        if mate is None:
            return
        traits = {}
        for key in agent.traits:
            base = (agent.traits[key] + mate.traits[key]) / 2
            traits[key] = max(0.1, min(2.0, base + (self.rng.random() - 0.5) * 0.1))
        personality = {k: max(0.0, min(1.0, (agent.personality[k] + mate.personality[k]) / 2 + (self.rng.random() - 0.5) * 0.1)) for k in PERSONALITY_KEYS}
        child = Agent(
            agent_id=self.next_agent_id,
            x=agent.x,
            y=agent.y,
            energy=60,
            age=0,
            max_age=int((agent.max_age + mate.max_age) / 2),
            health=100.0,
            generation=max(agent.generation, mate.generation) + 1,
            traits=traits,
            personality=personality,
            goals=["survive", "learn", "bond"],
            inventory={g: 1 for g in GOODS},
            skill=0.5 + traits["intelligence"] * 0.5,
        )
        self.next_agent_id += 1
        self.agents.append(child)
        self.agent_index[child.agent_id] = child
        agent.inventory["food"] -= 2
        mate.inventory["food"] -= 2
        agent.energy -= 10
        mate.energy -= 10
        self.events.append((self.tick, int(EventType.BIRTH), (agent.x, agent.y), child.agent_id))

    def step(self) -> Dict[str, Any]:
        self.tick += 1
        self.update_environment()
        debug_nodes = 0
        self._rebuild_spatial_index()
        agent_ids = sorted(a.agent_id for a in self.agents if a.alive)
        for agent_id in agent_ids:
            agent = self.agent_index[agent_id]
            if not agent.alive:
                continue
            agent.age += 1
            agent.energy -= 0.6
            if self.tick % 24 == 0:
                agent.inventory["food"] = max(0, agent.inventory["food"] - 1)
                if agent.inventory["food"] == 0:
                    agent.health -= 8
            decision = self._agent_decision(agent)
            if self.debug_enabled:
                agent.debug = {"tick": self.tick, "decision": decision, "inventory": dict(agent.inventory), "energy": round(agent.energy, 2)}
            if decision.startswith("gather_"):
                self._gather(agent, decision.split("_", 1)[1])
            elif decision == "social":
                self._social_or_conflict(agent)
            elif decision == "build":
                self._build(agent)
            elif decision == "reproduce":
                self._reproduce(agent)
            elif decision == "wander":
                target = ((agent.x + int(self.rng.random() * 7) - 3) % self.width, (agent.y + int(self.rng.random() * 7) - 3) % self.height)
                debug_nodes += self._move_agent_towards(agent, target)
            else:
                agent.energy += 1.5
                agent.health = min(100.0, agent.health + 0.5)
            if agent.health <= 0 or agent.age >= agent.max_age or agent.energy <= -20:
                agent.alive = False
                self.events.append((self.tick, int(EventType.DEATH), (agent.x, agent.y), agent.agent_id))
        self.update_economy()
        alive_count = sum(1 for a in self.agents if a.alive)
        self.population_trend.append(alive_count)
        return {
            "tick": self.tick,
            "alive": alive_count,
            "market": dict(self.market),
            "path_nodes_explored": debug_nodes,
            "resource_flow": dict(self.resource_flow),
        }

    def run(self, steps: int) -> Dict[str, Any]:
        summary = {}
        for _ in range(steps):
            summary = self.step()
        return summary

    def snapshot(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "initial_agents": self.initial_agents,
            "tick": self.tick,
            "rng_state": repr(self.rng.getstate()),
            "market": self.market,
            "resource_flow": dict(self.resource_flow),
            "population_trend": self.population_trend,
            "events": self.events,
            "grid": [[asdict(cell) for cell in row] for row in self.grid],
            "agents": [
                {
                    **{k: v for k, v in asdict(agent).items() if k != "memory"},
                    "memory": [asdict(m) for m in agent.memory],
                }
                for agent in self.agents
            ],
            "next_agent_id": self.next_agent_id,
        }

    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.snapshot(), separators=(",", ":")))

    @classmethod
    def load(cls, path: str) -> "DeterministicCivilizationSimulator":
        data = json.loads(Path(path).read_text())
        sim = cls(data["seed"], data["width"], data["height"], 0)
        sim.initial_agents = data["initial_agents"]
        sim.tick = data["tick"]
        sim.rng.setstate(ast.literal_eval(data["rng_state"]))
        sim.market = {k: float(v) for k, v in data["market"].items()}
        sim.resource_flow = Counter(data["resource_flow"])
        sim.population_trend = list(data["population_trend"])
        sim.events = [tuple(event) for event in data["events"]]
        sim.grid = [[Cell(**cell) for cell in row] for row in data["grid"]]
        sim.agents = []
        sim.agent_index = {}
        for agent_data in data["agents"]:
            agent_data = dict(agent_data)
            mem = [MemoryEntry(event_type=m["event_type"], location=tuple(m["location"]), timestamp=m["timestamp"], outcome=m["outcome"], info_quality=m.get("info_quality", 1.0)) for m in agent_data.pop("memory")]
            if agent_data.get("path_target") is not None:
                agent_data["path_target"] = tuple(agent_data["path_target"])
            agent_data["path"] = [tuple(step) for step in agent_data.get("path", [])]
            agent = Agent(**agent_data)
            agent.memory = mem
            sim.agents.append(agent)
            sim.agent_index[agent.agent_id] = agent
        sim.next_agent_id = data["next_agent_id"]
        return sim

    def digest(self) -> Dict[str, Any]:
        alive = [a for a in self.agents if a.alive]
        positions = sorted((a.agent_id, a.x, a.y) for a in alive[:50])
        totals = {g: sum(a.inventory[g] for a in alive) for g in GOODS}
        return {
            "tick": self.tick,
            "alive": len(alive),
            "positions": positions,
            "totals": totals,
            "events": len(self.events),
            "population_tail": self.population_trend[-10:],
            "market": self.market,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic distributed civilization simulator")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--agents", type=int, default=1000)
    parser.add_argument("--width", type=int, default=48)
    parser.add_argument("--height", type=int, default=32)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--save")
    parser.add_argument("--load")
    args = parser.parse_args()

    sim = DeterministicCivilizationSimulator.load(args.load) if args.load else DeterministicCivilizationSimulator(args.seed, args.width, args.height, args.agents, args.debug)
    summary = sim.run(args.steps)
    if args.save:
        sim.save(args.save)
    print(json.dumps({"summary": summary, "digest": sim.digest()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
