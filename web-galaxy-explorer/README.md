# Galaxy Explorer (HTML + Canvas)

An interactive, cinematic 3D spiral galaxy drawn with 9,000 stars on a plain HTML canvas. No libraries, just one file.

## Run it
Open `index.html` in any browser. You can also host it free on GitHub Pages.

## Interactions
- **Drag** to tilt and rotate the galaxy
- **Scroll** to zoom in and out
- **Click** anywhere to trigger a supernova
- **Arms** slider rebuilds the galaxy with 2–7 spiral arms
- **Spin** slider changes rotation speed
- **Hyperspace jump** zooms through with motion blur

## How it works
- Each star gets an arm, a distance from the core, and a twist angle, which forms the spiral shape
- Inner stars orbit faster than outer ones (differential rotation, like real galaxies)
- A simple 3D-to-2D perspective projection plus additive blending creates the glow
