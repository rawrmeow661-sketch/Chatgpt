# 2D Boat Simulation Game

A browser-based 2D physics sandbox featuring:

- Procedural waves (multi-sine ocean surface)
- Buoyancy and drag sampled across hull points
- Rigid-body boat motion with angular dynamics
- Destruction tools: push force, cannonball, timed mine explosions, and saw cutting

## How to launch it

### Option A (recommended): run a local web server

From the project folder:

```bash
python3 -m http.server 8000
```

Then open:

- `http://localhost:8000`

> If port `8000` is busy, use another port (for example `9000`):
>
> ```bash
> python3 -m http.server 9000
> ```
>
> and open `http://localhost:9000`.

### Option B: open directly

You can also open `index.html` directly in a browser (double-click file), but some browsers behave better when served through `http://localhost`.

## Controls

- **Push**: click-drag and release to apply impulse.
- **Cannonball**: click-drag and release to fire a projectile.
- **Mine**: click to place a timed explosive.
- **Saw**: click-drag through hull to cut it.
- **Reset Boat**: restores original boat state.
