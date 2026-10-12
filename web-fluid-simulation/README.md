# Fluid Simulation (WebGL2)

Real-time ink-in-water simulation that solves the **Navier–Stokes equations** on the GPU. Drag to stir glowing dye and watch it swirl, curl, and mix.

## Run it
Open `index.html` in Chrome, Edge, or Firefox (WebGL2 required). Works with mouse and touch, including several fingers at once.

| Control | Action |
|---|---|
| Drag | Stir the fluid and inject dye |
| Click | Radial splash |
| Pause / Reset | Freeze time / start fresh |
| Bloom | Toggle the glow |
| Show | Switch between the dye and the velocity field |

## How it works: Jos Stam's "Stable Fluids"
The fluid lives in floating-point textures. Each frame runs a chain of fragment shaders, where every pixel is one cell of the grid:

| Step | What it does |
|---|---|
| **Advection** | Moves velocity and dye along the flow by tracing each cell *backwards* in time (semi-Lagrangian, so it never blows up) |
| **Forces** | The mouse adds a Gaussian "splat" of velocity and color |
| **Vorticity confinement** | Measures the curl and pushes it back in, which keeps small swirls from fading away |
| **Divergence** | Measures how much fluid flows in vs. out of each cell |
| **Pressure solve** | 24 Jacobi iterations solve a Poisson equation for pressure (warm-started from the previous frame) |
| **Projection** | Subtracts the pressure gradient, so the fluid becomes incompressible: no cell gains or loses fluid |

Rendering adds fake lighting from the dye's gradient (an "ink" look), a 3-pass Gaussian **bloom**, and tone mapping.

Each texture uses **ping-pong buffers**: read from one, write to the other, then swap, because a GPU can't read and write the same texture at once.
