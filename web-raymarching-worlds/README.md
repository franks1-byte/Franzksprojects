# Raymarching Worlds (WebGL2 + GLSL)

Three real-time 3D scenes rendered **entirely inside a fragment shader**: no meshes, no 3D models, no libraries. Every pixel shoots a ray and "marches" it through mathematical shapes described by **signed distance functions (SDFs)**.

## Scenes
| Scene | Technique shown |
|---|---|
| **Mandelbulb** | 3D fractal with a "breathing" power, colored by an orbit trap |
| **Infinite Pillars** | Domain repetition turns one pillar into an endless field with glowing orbs |
| **Liquid Metal** | Metaballs blended with smooth-min, plus chrome reflections and Fresnel |

## Run it
Open `index.html` in Chrome, Edge, or Firefox. It needs WebGL2, which almost every browser supports. You can also host it on GitHub Pages.

**Controls:** drag to orbit, scroll to zoom, and click the buttons to switch scenes.

## Rendering features
- **Sphere tracing**: step along each ray by the distance to the nearest surface
- **Normals** from the SDF gradient (finite differences)
- **Soft shadows** by tracking how closely a shadow ray passes geometry
- **Ambient occlusion** sampled along the normal
- **Specular, Fresnel rim light, and reflections**
- **Distance fog, tone mapping, gamma correction, and a vignette**
- **Adaptive resolution**: render scale drops automatically when FPS falls below 30, so it stays smooth on weaker GPUs

## How raymarching works
```
for each pixel:
    ray = camera → pixel
    t = 0
    repeat:
        d = distance from (origin + ray * t) to the nearest surface
        if d is tiny: we hit something, so shade it
        t += d        # it is safe to step this far without passing through anything
```
