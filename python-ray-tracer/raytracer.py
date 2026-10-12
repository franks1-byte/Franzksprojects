"""
A physically-based path tracer written with numpy.

Every pixel shoots many random rays that bounce around the scene, picking up color from each surface
they hit. Averaging them produces realistic soft shadows, color bleeding, reflections, refraction,
depth of field, and glowing lights, all from a few hundred lines of code.

Materials: diffuse (Lambertian), metal (with roughness), glass (dielectric with Fresnel/Schlick),
and emissive lights. The rays are vectorized: whole arrays of rays are traced at once with numpy,
which makes pure Python fast enough to render in seconds.

Run:  python raytracer.py                  (quick preview)
      python raytracer.py --spp 256 --width 960   (high quality)
"""
import argparse
import time

import numpy as np

# ---------------------------------------------------------------- vector helpers
def normalize(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def dot(a, b):
    return np.sum(a * b, axis=-1)


DIFFUSE, METAL, GLASS, LIGHT = 0, 1, 2, 3


class Scene:
    """Spheres only, stored as parallel numpy arrays so we can intersect every ray with every sphere at once."""

    def __init__(self):
        self.centers, self.radii, self.colors, self.kinds, self.params = [], [], [], [], []

    def add(self, center, radius, color, kind=DIFFUSE, param=0.0):
        # param: roughness for metal, refractive index for glass, strength for light
        self.centers.append(center)
        self.radii.append(radius)
        self.colors.append(color)
        self.kinds.append(kind)
        self.params.append(param)

    def freeze(self):
        self.C = np.array(self.centers, dtype=np.float64)
        self.R = np.array(self.radii, dtype=np.float64)
        self.col = np.array(self.colors, dtype=np.float64)
        self.kind = np.array(self.kinds)
        self.param = np.array(self.params, dtype=np.float64)

    def intersect(self, origins, dirs):
        """Returns (t, sphere index) of the nearest hit for every ray; index -1 for misses."""
        oc = origins[:, None, :] - self.C[None, :, :]          # (rays, spheres, 3)
        b = np.einsum("rsk,rk->rs", oc, dirs)
        c = np.einsum("rsk,rsk->rs", oc, oc) - self.R[None, :] ** 2
        disc = b * b - c
        hit = disc > 0
        sq = np.sqrt(np.where(hit, disc, 0))
        t0, t1 = -b - sq, -b + sq
        eps = 1e-4
        t = np.where(t0 > eps, t0, np.where(t1 > eps, t1, np.inf))   # nearest hit in front of the ray
        t = np.where(hit, t, np.inf)
        idx = np.argmin(t, axis=1)
        best = t[np.arange(len(t)), idx]
        idx = np.where(np.isfinite(best), idx, -1)
        return best, idx


def random_unit_vectors(n, rng):
    v = rng.normal(size=(n, 3))
    return normalize(v)


def sky(dirs):
    """Dark gradient sky with a faint glow, so the lights in the scene do most of the work."""
    t = 0.5 * (dirs[:, 1] + 1.0)
    return (1 - t)[:, None] * np.array([0.05, 0.05, 0.09]) + t[:, None] * np.array([0.16, 0.20, 0.34])


def trace(scene, origins, dirs, rng, max_bounces=8):
    n = len(origins)
    color = np.zeros((n, 3))
    throughput = np.ones((n, 3))     # how much light still survives along each path
    alive = np.arange(n)

    for bounce in range(max_bounces):
        if len(alive) == 0:
            break
        o, d = origins[alive], dirs[alive]
        t, idx = scene.intersect(o, d)

        miss = idx < 0
        color[alive[miss]] += throughput[alive[miss]] * sky(d[miss])
        keep = ~miss
        alive, o, d, t, idx = alive[keep], o[keep], d[keep], t[keep], idx[keep]
        if len(alive) == 0:
            break

        p = o + d * t[:, None]
        normal = normalize(p - scene.C[idx])
        front = dot(d, normal) < 0                       # did we hit the outside of the sphere?
        n_face = np.where(front[:, None], normal, -normal)
        kind = scene.kind[idx]
        albedo = scene.col[idx]
        param = scene.param[idx]

        # lights add their glow and end the path
        is_light = kind == LIGHT
        color[alive[is_light]] += throughput[alive[is_light]] * albedo[is_light] * param[is_light, None]

        new_dir = np.zeros_like(d)
        # diffuse: random bounce biased toward the normal (cosine-weighted)
        m = kind == DIFFUSE
        new_dir[m] = normalize(n_face[m] + random_unit_vectors(m.sum(), rng))
        # metal: mirror reflection, blurred by roughness
        m = kind == METAL
        refl = d[m] - 2 * dot(d[m], n_face[m])[:, None] * n_face[m]
        new_dir[m] = normalize(refl + param[m, None] * random_unit_vectors(m.sum(), rng))
        # glass: refract or reflect depending on angle (Snell's law + Schlick's Fresnel approximation)
        m = kind == GLASS
        if m.any():
            ratio = np.where(front[m], 1.0 / param[m], param[m])
            cos_t = np.minimum(-dot(d[m], n_face[m]), 1.0)
            sin_t = np.sqrt(1.0 - cos_t ** 2)
            r0 = ((1 - ratio) / (1 + ratio)) ** 2
            schlick = r0 + (1 - r0) * (1 - cos_t) ** 5
            reflect = (ratio * sin_t > 1.0) | (schlick > rng.random(m.sum()))   # total internal reflection or Fresnel
            perp = ratio[:, None] * (d[m] + cos_t[:, None] * n_face[m])
            parallel = -np.sqrt(np.abs(1.0 - dot(perp, perp)))[:, None] * n_face[m]
            refr = perp + parallel
            refl = d[m] - 2 * dot(d[m], n_face[m])[:, None] * n_face[m]
            new_dir[m] = normalize(np.where(reflect[:, None], refl, refr))

        # metal rays that scattered below the surface are absorbed
        absorbed = (kind == METAL) & (dot(new_dir, n_face) <= 0)
        cont = ~is_light & ~absorbed
        throughput[alive] *= np.where((kind == GLASS)[:, None], 1.0, albedo)

        # Russian roulette: randomly stop dim paths, boosting survivors so the average stays correct
        if bounce >= 3:
            survive_p = np.clip(throughput[alive].max(axis=1), 0.05, 1.0)
            lucky = rng.random(len(alive)) < survive_p
            throughput[alive] /= survive_p[:, None]
            cont &= lucky

        origins[alive[cont]] = p[cont] + n_face[cont] * np.where((kind[cont] == GLASS)[:, None] & (dot(new_dir[cont], n_face[cont]) < 0)[:, None], -1e-3, 1e-3)
        dirs[alive[cont]] = new_dir[cont]
        alive = alive[cont]

    return color


class Camera:
    def __init__(self, look_from, look_at, fov, aspect, aperture, focus_dist):
        theta = np.radians(fov)
        h = np.tan(theta / 2)
        self.origin = np.array(look_from, dtype=float)
        w = normalize(self.origin - np.array(look_at, dtype=float))
        self.u = normalize(np.cross([0, 1, 0], w))
        self.v = np.cross(w, self.u)
        vh = 2 * h * focus_dist
        vw = aspect * vh
        self.horizontal = vw * self.u
        self.vertical = vh * self.v
        self.lower_left = self.origin - self.horizontal / 2 - self.vertical / 2 - focus_dist * w
        self.lens_radius = aperture / 2

    def rays(self, s, t, rng):
        """s, t in [0,1]; the lens offset gives depth of field (things off the focus plane blur)."""
        rd = self.lens_radius * rng.normal(size=(len(s), 2)) * 0.5
        offset = rd[:, :1] * self.u + rd[:, 1:] * self.v
        origins = self.origin + offset
        dirs = normalize(self.lower_left + s[:, None] * self.horizontal + t[:, None] * self.vertical - origins)
        return origins, dirs


def build_scene(seed=3):
    rng = np.random.default_rng(seed)
    s = Scene()
    s.add([0, -1000, 0], 1000, [0.45, 0.45, 0.5])                        # ground
    s.add([0, 1, 0], 1.0, [1, 1, 1], GLASS, 1.5)                         # glass ball
    s.add([0, 1, 0], -0.92, [1, 1, 1], GLASS, 1.5)                       # hollow inside (negative radius flips normals)
    s.add([-2.2, 1, -0.6], 1.0, [0.95, 0.75, 0.4], METAL, 0.02)          # gold mirror
    s.add([2.2, 1, -0.6], 1.0, [0.85, 0.3, 0.45], DIFFUSE)               # matte pink
    s.add([0.0, 6.0, -1.5], 2.4, [1.0, 0.85, 0.7], LIGHT, 4.0)           # warm key light
    s.add([-4.5, 0.6, 2.2], 0.6, [0.35, 0.95, 1.0], LIGHT, 6.0)          # cyan accent light
    s.add([4.2, 0.5, 2.6], 0.5, [1.0, 0.3, 0.85], LIGHT, 6.0)            # pink accent light
    # scattered small spheres
    for _ in range(26):
        r = rng.uniform(0.15, 0.3)
        x, z = rng.uniform(-6, 6), rng.uniform(-4, 4)
        if abs(x) < 3.3 and -1.8 < z < 1.2:
            continue
        roll = rng.random()
        color = rng.uniform(0.2, 1.0, 3)
        if roll < 0.55:
            s.add([x, r, z], r, color)
        elif roll < 0.85:
            s.add([x, r, z], r, color, METAL, rng.uniform(0, 0.3))
        else:
            s.add([x, r, z], r, [1, 1, 1], GLASS, 1.5)
    s.freeze()
    return s


def render(width=480, height=270, spp=48, seed=0, chunk=40000):
    rng = np.random.default_rng(seed)
    scene = build_scene()
    cam = Camera(look_from=[0, 2.3, 7.5], look_at=[0, 0.9, 0], fov=38, aspect=width / height,
                 aperture=0.12, focus_dist=np.linalg.norm(np.array([0, 2.3, 7.5]) - np.array([0, 1, 0])))
    ys, xs = np.mgrid[0:height, 0:width]
    xs, ys = xs.ravel().astype(float), ys.ravel().astype(float)
    accum = np.zeros((width * height, 3))
    start = time.time()
    for sample in range(spp):
        # jitter inside each pixel = free anti-aliasing
        s = (xs + rng.random(len(xs))) / width
        t = 1 - (ys + rng.random(len(ys))) / height
        for i in range(0, len(xs), chunk):
            o, d = cam.rays(s[i:i + chunk], t[i:i + chunk], rng)
            accum[i:i + chunk] += trace(scene, o, d, rng)
        done = sample + 1
        eta = (time.time() - start) / done * (spp - done)
        print(f"\r  sample {done}/{spp}  ({eta:.0f}s left)  ", end="", flush=True)
    print()
    img = accum / spp
    img = img / (1 + img)                     # Reinhard tone mapping (keeps bright lights from clipping harshly)
    img = np.clip(img, 0, 1) ** (1 / 2.2)      # gamma correction
    return (img.reshape(height, width, 3) * 255).astype(np.uint8)


def save_png(path, pixels):
    """Write a PNG with only the standard library (zlib + struct), with no imaging library needed."""
    import struct
    import zlib
    h, w, _ = pixels.shape
    raw = b"".join(b"\x00" + pixels[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="numpy path tracer")
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--spp", type=int, default=48, help="samples per pixel (more = less noise, slower)")
    ap.add_argument("--out", default="render.png")
    a = ap.parse_args()
    height = a.width * 9 // 16
    print(f"Rendering {a.width}x{height} at {a.spp} samples per pixel…")
    t0 = time.time()
    save_png(a.out, render(a.width, height, a.spp))
    print(f"Saved {a.out} in {time.time() - t0:.1f}s")
