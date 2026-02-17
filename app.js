const canvas = document.getElementById('sim');
const ctx = canvas.getContext('2d');
const statsEl = document.getElementById('stats');

const GRAVITY = 980;
const WATER_DENSITY = 0.0026;
const LINEAR_DAMPING = 0.998;
const ANGULAR_DAMPING = 0.995;
const WAVE_BASE = 460;

const state = {
  t: 0,
  tool: 'push',
  dragging: false,
  dragStart: null,
  particles: [],
  projectiles: [],
  mines: [],
};

const wave = {
  components: [
    { amp: 18, freq: 0.012, speed: 1.2 },
    { amp: 10, freq: 0.022, speed: -0.7 },
    { amp: 7, freq: 0.033, speed: 1.8 },
  ],
  heightAt(x, t) {
    return WAVE_BASE + this.components.reduce((sum, c) => sum + c.amp * Math.sin(x * c.freq + t * c.speed), 0);
  },
  velocityAt(x, t) {
    return this.components.reduce((sum, c) => sum + c.amp * c.speed * Math.cos(x * c.freq + t * c.speed), 0);
  },
};

class Boat {
  constructor() {
    this.reset();
  }

  reset() {
    this.pos = { x: 520, y: 380 };
    this.vel = { x: 0, y: 0 };
    this.angle = -0.1;
    this.omega = 0;
    this.mass = 120;
    this.inertia = 3.2e6;

    this.vertices = [
      { x: -170, y: -18, hp: 1 },
      { x: -140, y: 18, hp: 1 },
      { x: -90, y: 36, hp: 1 },
      { x: -35, y: 44, hp: 1 },
      { x: 20, y: 46, hp: 1 },
      { x: 90, y: 40, hp: 1 },
      { x: 145, y: 22, hp: 1 },
      { x: 170, y: -16, hp: 1 },
      { x: 95, y: -36, hp: 1 },
      { x: 20, y: -42, hp: 1 },
      { x: -70, y: -38, hp: 1 },
    ];
  }

  getAliveVertices() {
    return this.vertices.filter((v) => v.hp > 0.05);
  }

  worldPoint(local) {
    const c = Math.cos(this.angle);
    const s = Math.sin(this.angle);
    return {
      x: this.pos.x + local.x * c - local.y * s,
      y: this.pos.y + local.x * s + local.y * c,
    };
  }

  velocityAtPoint(local) {
    return {
      x: this.vel.x - this.omega * local.y,
      y: this.vel.y + this.omega * local.x,
    };
  }

  applyForce(force, local, dt) {
    this.vel.x += (force.x / this.mass) * dt;
    this.vel.y += (force.y / this.mass) * dt;
    const torque = local.x * force.y - local.y * force.x;
    this.omega += (torque / this.inertia) * dt;
  }

  applyImpulse(impulse, local) {
    this.vel.x += impulse.x / this.mass;
    this.vel.y += impulse.y / this.mass;
    const torque = local.x * impulse.y - local.y * impulse.x;
    this.omega += torque / this.inertia;
  }

  step(dt, t) {
    this.applyForce({ x: 0, y: this.mass * GRAVITY }, { x: 0, y: 0 }, dt);

    const alive = this.getAliveVertices();
    for (const v of alive) {
      const world = this.worldPoint(v);
      const waterY = wave.heightAt(world.x, t);
      const depth = waterY - world.y;
      if (depth > 0) {
        const pointVel = this.velocityAtPoint(v);
        const fluidVx = wave.velocityAt(world.x, t) * 4;
        const relX = fluidVx - pointVel.x;
        const relY = -pointVel.y;

        const buoyancy = WATER_DENSITY * depth * depth * (90 + 70 * v.hp);
        const drag = 0.48;

        this.applyForce(
          {
            x: relX * drag * depth,
            y: -buoyancy + relY * drag * depth,
          },
          v,
          dt,
        );
      }
    }

    this.vel.x *= LINEAR_DAMPING;
    this.vel.y *= LINEAR_DAMPING;
    this.omega *= ANGULAR_DAMPING;

    this.pos.x += this.vel.x * dt;
    this.pos.y += this.vel.y * dt;
    this.angle += this.omega * dt;

    if (this.pos.y > canvas.height + 400) this.reset();
  }

  draw(ctx) {
    const alive = this.getAliveVertices();
    if (alive.length < 3) return;

    ctx.beginPath();
    alive.forEach((v, i) => {
      const w = this.worldPoint(v);
      if (i === 0) ctx.moveTo(w.x, w.y);
      else ctx.lineTo(w.x, w.y);
    });
    ctx.closePath();

    const stress = Math.min(1, Math.abs(this.omega) * 8 + Math.hypot(this.vel.x, this.vel.y) / 1500);
    ctx.fillStyle = `hsl(${35 - stress * 25} 88% ${68 - stress * 15}%)`;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = 'rgba(0,0,0,0.4)';
    ctx.stroke();

    for (const v of this.vertices) {
      if (v.hp <= 0.05) continue;
      const w = this.worldPoint(v);
      ctx.fillStyle = `rgba(255,255,255,${0.25 * v.hp})`;
      ctx.beginPath();
      ctx.arc(w.x, w.y, 2.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  damageAt(worldX, worldY, radius, amount) {
    for (const v of this.vertices) {
      if (v.hp <= 0) continue;
      const p = this.worldPoint(v);
      const d = Math.hypot(worldX - p.x, worldY - p.y);
      if (d < radius) {
        v.hp -= amount * (1 - d / radius);
      }
    }
  }
}

const boat = new Boat();

function resize() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

function screenToCanvas(e) {
  const rect = canvas.getBoundingClientRect();
  return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

function setTool(tool) {
  state.tool = tool;
  document.querySelectorAll('[data-tool]').forEach((btn) => btn.classList.toggle('active', btn.dataset.tool === tool));
}

document.querySelectorAll('[data-tool]').forEach((btn) => btn.addEventListener('click', () => setTool(btn.dataset.tool)));
document.getElementById('reset').addEventListener('click', () => {
  boat.reset();
  state.projectiles = [];
  state.mines = [];
  state.particles = [];
});

canvas.addEventListener('mousedown', (e) => {
  state.dragging = true;
  state.dragStart = screenToCanvas(e);
});

canvas.addEventListener('mouseup', (e) => {
  const end = screenToCanvas(e);
  if (!state.dragStart) return;
  const start = state.dragStart;
  state.dragging = false;

  if (state.tool === 'push') {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const local = {
      x: (start.x - boat.pos.x) * Math.cos(-boat.angle) - (start.y - boat.pos.y) * Math.sin(-boat.angle),
      y: (start.x - boat.pos.x) * Math.sin(-boat.angle) + (start.y - boat.pos.y) * Math.cos(-boat.angle),
    };
    boat.applyImpulse({ x: dx * 0.7, y: dy * 0.7 }, local);
  } else if (state.tool === 'cannon') {
    const v = { x: (end.x - start.x) * 2.7, y: (end.y - start.y) * 2.7 };
    state.projectiles.push({ x: start.x, y: start.y, vx: v.x, vy: v.y, r: 6, life: 8 });
  } else if (state.tool === 'mine') {
    state.mines.push({ x: start.x, y: start.y, timer: 1.2, r: 16 });
  } else if (state.tool === 'saw') {
    const cuts = 20;
    for (let i = 0; i <= cuts; i++) {
      const a = i / cuts;
      const x = start.x + (end.x - start.x) * a;
      const y = start.y + (end.y - start.y) * a;
      boat.damageAt(x, y, 20, 0.2);
    }
  }

  state.dragStart = null;
});

function explode(x, y, power = 1) {
  boat.damageAt(x, y, 130 * power, 0.9 * power);
  const local = {
    x: (x - boat.pos.x) * Math.cos(-boat.angle) - (y - boat.pos.y) * Math.sin(-boat.angle),
    y: (x - boat.pos.x) * Math.sin(-boat.angle) + (y - boat.pos.y) * Math.cos(-boat.angle),
  };

  const dist = Math.max(50, Math.hypot(local.x, local.y));
  const impulseMag = (8000 * power) / dist;
  boat.applyImpulse({ x: (local.x / dist) * impulseMag, y: (local.y / dist) * impulseMag }, local);

  for (let i = 0; i < 45; i++) {
    const a = Math.random() * Math.PI * 2;
    const s = 120 + Math.random() * 280;
    state.particles.push({
      x,
      y,
      vx: Math.cos(a) * s,
      vy: Math.sin(a) * s,
      life: 1 + Math.random() * 0.8,
      maxLife: 1.8,
    });
  }
}

let last = performance.now();
function frame(now) {
  const dt = Math.min(1 / 30, (now - last) / 1000);
  last = now;
  state.t += dt;

  boat.step(dt, state.t);

  for (const p of state.projectiles) {
    p.vy += GRAVITY * dt;
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.life -= dt;

    const dBoat = Math.hypot(p.x - boat.pos.x, p.y - boat.pos.y);
    if (dBoat < 220) {
      boat.damageAt(p.x, p.y, 40, 0.45);
      const local = {
        x: (p.x - boat.pos.x) * Math.cos(-boat.angle) - (p.y - boat.pos.y) * Math.sin(-boat.angle),
        y: (p.x - boat.pos.x) * Math.sin(-boat.angle) + (p.y - boat.pos.y) * Math.cos(-boat.angle),
      };
      boat.applyImpulse({ x: p.vx * 0.06, y: p.vy * 0.06 }, local);
      p.life = -1;
    }
  }
  state.projectiles = state.projectiles.filter((p) => p.life > 0 && p.y < canvas.height + 40);

  for (const m of state.mines) {
    m.timer -= dt;
    if (m.timer <= 0) {
      explode(m.x, m.y, 1);
      m.timer = -1;
    }
  }
  state.mines = state.mines.filter((m) => m.timer > 0);

  for (const p of state.particles) {
    p.vy += 380 * dt;
    p.vx *= 0.99;
    p.vy *= 0.99;
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.life -= dt;
  }
  state.particles = state.particles.filter((p) => p.life > 0);

  draw();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

function drawWater() {
  ctx.beginPath();
  ctx.moveTo(0, canvas.height);
  for (let x = 0; x <= canvas.width; x += 8) {
    ctx.lineTo(x, wave.heightAt(x, state.t));
  }
  ctx.lineTo(canvas.width, canvas.height);
  ctx.closePath();

  const grad = ctx.createLinearGradient(0, 300, 0, canvas.height);
  grad.addColorStop(0, 'rgba(66, 146, 212, 0.62)');
  grad.addColorStop(1, 'rgba(18, 62, 101, 0.95)');
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  for (let x = 0; x <= canvas.width; x += 8) {
    const y = wave.heightAt(x, state.t);
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = 'rgba(155,220,255,0.75)';
  ctx.lineWidth = 2;
  ctx.stroke();
}

function drawSky() {
  const g = ctx.createLinearGradient(0, 0, 0, canvas.height);
  g.addColorStop(0, '#0a1020');
  g.addColorStop(1, '#1a2744');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function draw() {
  drawSky();
  drawWater();

  for (const mine of state.mines) {
    ctx.fillStyle = mine.timer < 0.3 ? '#ff7a7a' : '#d1e2ff';
    ctx.beginPath();
    ctx.arc(mine.x, mine.y, mine.r, 0, Math.PI * 2);
    ctx.fill();
  }

  for (const p of state.projectiles) {
    ctx.fillStyle = '#222';
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fill();
  }

  for (const p of state.particles) {
    const alpha = Math.max(0, p.life / p.maxLife);
    ctx.fillStyle = `rgba(255,160,70,${alpha})`;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2.2, 0, Math.PI * 2);
    ctx.fill();
  }

  boat.draw(ctx);

  if (state.dragging && state.dragStart) {
    ctx.strokeStyle = 'rgba(255,255,255,0.7)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(state.dragStart.x, state.dragStart.y);
    const mouse = window._mousePos || state.dragStart;
    ctx.lineTo(mouse.x, mouse.y);
    ctx.stroke();
  }

  const integrity = (boat.vertices.reduce((s, v) => s + Math.max(0, v.hp), 0) / boat.vertices.length) * 100;
  statsEl.textContent = `Tool=${state.tool} | Integrity=${integrity.toFixed(0)}% | v=(${boat.vel.x.toFixed(1)}, ${boat.vel.y.toFixed(1)}) | ω=${boat.omega.toFixed(3)}`;
}

canvas.addEventListener('mousemove', (e) => {
  window._mousePos = screenToCanvas(e);
});
