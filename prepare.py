#!/usr/bin/env python3
"""Build the bait-ball scene (Vork, GPU compute simulation).

A bait ball of silvery fish mills over a sunlit reef floor. The school is
simulated by scene-owned Slang compute programs (initialize -> clear -> grid ->
advance -> place) exactly as Vork's own examples do; this script writes the
scene JSON, the shaders, and zero-filled binary buffer sources.

No external assets: the water is a procedural environment program, and colour
absorption is done per-material (this release has no participating medium).

Usage:  python3 prepare.py
"""

import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCENE = ROOT / "scene"

N = 12000                                   # fish
GRID_DIM = (64, 32, 64)                     # cells (x, y, z), 0.75 m each
GRID_COUNT = GRID_DIM[0] * GRID_DIM[1] * GRID_DIM[2] * 4
GRID_MIN = (-24.0, 0.0, -24.0)
CELL = 0.75

# Sun: high and slightly to the side. Same direction drives the water shader and
# the sun light, so the glint in the environment matches the shadow caster.
SUN_ELEVATION = 1.05
SUN_ROTATION = 0.5
SUN_DISTANCE = 150.0


def r3(v):
    return [round(float(x), 6) for x in v]


def sun_direction():
    e, r = SUN_ELEVATION, SUN_ROTATION
    d = [math.cos(e) * math.sin(r), math.sin(e), -math.cos(e) * math.cos(r)]
    L = math.sqrt(sum(t * t for t in d))
    return [t / L for t in d]


# --------------------------------------------------------------------------- #
# Fish geometry: a low-poly fusiform body with caudal, dorsal, anal and
# pectoral fins. +Z is forward, +Y is up; the real length is ~1.12 units.
# --------------------------------------------------------------------------- #
def fish_geometry():
    nose = (0.0, 0.0, 0.50)
    top = (0.0, 0.10, 0.05)
    right = (0.07, 0.0, 0.05)
    bot = (0.0, -0.10, 0.05)
    left = (-0.07, 0.0, 0.05)
    tail = (0.0, 0.0, -0.45)

    AXIS_HINT = "axis"
    tris = [
        ((nose, top, right), AXIS_HINT),
        ((nose, right, bot), AXIS_HINT),
        ((nose, bot, left), AXIS_HINT),
        ((nose, left, top), AXIS_HINT),
        ((tail, top, right), AXIS_HINT),
        ((tail, right, bot), AXIS_HINT),
        ((tail, bot, left), AXIS_HINT),
        ((tail, left, top), AXIS_HINT),
        # caudal fin
        ((tail, (0.0, 0.16, -0.62), (0.0, 0.0, -0.55)), (1.0, 0.0, 0.0)),
        ((tail, (0.0, 0.0, -0.55), (0.0, -0.16, -0.62)), (1.0, 0.0, 0.0)),
        # dorsal / anal fins
        (((0.0, 0.10, 0.05), (0.0, 0.22, -0.10), (0.0, 0.10, -0.28)), (1.0, 0.0, 0.0)),
        (((0.0, -0.10, 0.05), (0.0, -0.20, -0.05), (0.0, -0.10, -0.28)), (1.0, 0.0, 0.0)),
        # pectoral fins
        (((-0.05, 0.0, 0.12), (-0.20, -0.03, -0.05), (-0.05, -0.02, -0.05)), (0.0, 1.0, 0.0)),
        (((0.05, 0.0, 0.12), (0.05, -0.02, -0.05), (0.20, -0.03, -0.05)), (0.0, 1.0, 0.0)),
    ]

    pos, nor, idx = [], [], []
    for verts, hint in tris:
        a, b, cc = verts
        u = [b[i] - a[i] for i in range(3)]
        v = [cc[i] - a[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        L = math.sqrt(sum(t * t for t in n)) or 1.0
        n = [t / L for t in n]
        if hint == AXIS_HINT:
            cx = sum(p[0] for p in verts) / 3.0
            cz = sum(p[2] for p in verts) / 3.0
            ref = (-cx, 0.0, -cz)
        else:
            ref = hint
        if sum(n[i] * ref[i] for i in range(3)) < 0.0:
            verts = (a, cc, b)
            n = [-t for t in n]
        base = len(pos)
        pos += [r3(p) for p in verts]
        nor += [r3(n)] * 3
        idx += [base, base + 1, base + 2]
    return pos, nor, idx


# --------------------------------------------------------------------------- #
# Reef floor: a wide, gently dune-shaped sand plain with smooth normals.
# --------------------------------------------------------------------------- #
def seabed_geometry(half=70.0, seg=72):
    def h(x, z):
        return (0.80 * math.sin(x * 0.09) * math.sin(z * 0.07)
                + 0.35 * math.sin(x * 0.21 + 1.7) * math.sin(z * 0.19 - 0.6)
                + 0.14 * math.sin(x * 0.55) * math.sin(z * 0.5))

    step = (2 * half) / seg
    pos, nor, idx = [], [], []
    for iz in range(seg + 1):
        for ix in range(seg + 1):
            x = -half + ix * step
            z = -half + iz * step
            pos.append([round(x, 4), round(h(x, z), 4), round(z, 4)])
    for iz in range(seg):
        for ix in range(seg):
            a = iz * (seg + 1) + ix
            b = a + 1
            c = a + (seg + 1)
            d = c + 1
            idx += [a, c, b, b, c, d]
    dx = 0.5 * step
    for p in pos:
        x, z = p[0], p[2]
        nx = -(h(x + dx, z) - h(x - dx, z)) / (2 * dx)
        nz = -(h(x, z + dx) - h(x, z - dx)) / (2 * dx)
        n = [nx, 1.0, nz]
        L = math.sqrt(sum(t * t for t in n))
        nor.append([round(t / L, 5) for t in n])
    return pos, nor, idx


# --------------------------------------------------------------------------- #
# Camera: a slow arc around the ball, looking just past it at the surface band.
# --------------------------------------------------------------------------- #
def roost(t):
    # Must match advance.slang: a fixed point the school mills around.
    return (0.0, 9.0, 0.0)


def camera_track(t0=0.0, t1=20.0, keys=241):
    cam, aim = [], []
    for k in range(keys):
        u = k / (keys - 1)
        t = t0 + (t1 - t0) * u
        c = roost(t)
        a = -0.80 + u * 1.60
        r = 24.0 - 2.5 * math.sin((t - t0) * 0.5)
        # Camera near the ball's own level, looking just past it: the school
        # fills the frame, bright water above, the reef as a band below.
        hy = -1.0 + 1.0 * math.sin((t - t0) * 0.3)
        cam.append([t, [round(c[0] + r * math.sin(a), 4),
                        round(c[1] + hy, 4),
                        round(c[2] + r * math.cos(a), 4)]])
        aim.append([t, [round(c[0], 4), round(c[1] + 0.5, 4), round(c[2], 4)]])
    return cam, aim


def build_scene():
    fish_p, fish_n, fish_i = fish_geometry()
    reef_p, reef_n, reef_i = seabed_geometry()
    sun = sun_direction()
    sun_pos = [round(sun[i] * SUN_DISTANCE, 4) for i in range(3)]
    sun_pos[1] += 4.0

    sim_state = ["p", "v", "next_p", "next_v", "translation", "rotation", "scale", "grid"]

    scene = {
        "version": 2,
        "buffers": {
            "p": {"type": "vec3", "file": "state.bin", "count": N},
            "v": {"type": "vec3", "file": "state.bin", "count": N},
            "next_p": {"type": "vec3", "file": "state.bin", "count": N},
            "next_v": {"type": "vec3", "file": "state.bin", "count": N},
            "translation": {"type": "vec3", "file": "state.bin", "count": N},
            "rotation": {"type": "vec4", "file": "rotation.bin", "count": N},
            "scale": {"type": "vec3", "file": "state.bin", "count": N},
            "grid": {"type": "u32", "file": "grid.bin", "count": GRID_COUNT},
            "fish_p": {"type": "vec3", "data": fish_p},
            "fish_n": {"type": "vec3", "data": fish_n},
            "fish_i": {"type": "u32", "data": fish_i},
            "reef_p": {"type": "vec3", "data": reef_p},
            "reef_n": {"type": "vec3", "data": reef_n},
            "reef_i": {"type": "u32", "data": reef_i},
        },
        "programs": {
            "initialize": {"file": "initialize.slang", "schedule": "simulation",
                           "dispatch": N,
                           "bindings": {"p": "p", "v": "v", "translation": "translation",
                                        "rotation": "rotation", "scale": "scale"}},
            "clear": {"file": "clear.slang", "schedule": "simulation",
                      "dispatch": GRID_COUNT, "bindings": {"grid": "grid"}},
            "grid": {"file": "grid.slang", "schedule": "simulation", "dispatch": N,
                     "bindings": {"p": "p", "grid": "grid"}},
            "advance": {"file": "advance.slang", "schedule": "simulation", "dispatch": N,
                        "bindings": {"p": "p", "v": "v", "grid": "grid",
                                     "next_p": "next_p", "next_v": "next_v"}},
            "place": {"file": "place.slang", "schedule": "simulation", "dispatch": N,
                      "bindings": {"p": "p", "v": "v", "next_p": "next_p",
                                   "next_v": "next_v", "translation": "translation",
                                   "rotation": "rotation"}},
            "fish": {"file": "fish.slang"},
            "seabed": {"file": "seabed.slang"},
            "water": {"file": "water.slang"},
        },
        "geometry": {
            "fish": {"attributes": {"POSITION": "fish_p", "NORMAL": "fish_n"},
                     "indices": "fish_i"},
            "reef": {"attributes": {"POSITION": "reef_p", "NORMAL": "reef_n"},
                     "indices": "reef_i"},
        },
        "materials": {
            "fish": {"program": "fish", "inputs": {"glint": 0.95, "eye": [0.0, 7.0, 22.0]}},
            "seabed": {"program": "seabed", "inputs": {"eye": [0.0, 7.0, 22.0]}},
            "water": {"program": "water", "inputs": {"sun_dir": r3(sun)}},
            "camera-optics": {"program": "std/camera", "inputs": {
                "lens": 32.0, "clip_start": 0.1, "clip_end": 4000.0,
                "use_dof": False, "aperture_fstop": 4.0}},
        },
        "simulation": {
            "t0": 0.0, "dt": 1.0 / 60.0, "seed": 11,
            "state": sim_state,
            "init": ["initialize"],
            "steps": ["clear", "grid", "advance", "place"],
        },
        "nodes": [
            {"type": "mesh", "name": "school", "geometry": "fish", "materials": ["fish"],
             "instances": {"attributes": {"TRANSLATION": "translation",
                                          "ROTATION": "rotation", "SCALE": "scale"}}},
            {"type": "mesh", "name": "reef", "geometry": "reef", "materials": ["seabed"]},
            {"type": "node", "name": "aim", "translation": [0.0, 8.0, 0.0]},
            {"type": "camera", "name": "camera", "translation": [0.0, 7.0, 26.0],
             "target": "aim", "material": "camera-optics"},
            # Sun from above, filtered by the water; direction matches water.slang.
            {"type": "light", "name": "sun", "shape": "sun",
             "translation": [sun_pos[0], sun_pos[1], sun_pos[2]], "target": [0.0, 4.0, 0.0],
             "energy": 3.0, "color": [0.72, 0.90, 1.00], "angle": 0.02},
            {"type": "light", "name": "water", "shape": "environment",
             "energy": 1.00, "material": "water"},
        ],
        "animation": [],
        "render": {
            "resolution": [1920, 1080], "fps": 24, "duration": 24.0,
            "background": "environment",
            "display": {"program": "std/agx", "inputs": {"exposure": 0.0}},
            "motion_blur": {"shutter": 0.4, "position": "center"},
        },
    }

    cam, aim = camera_track()
    scene["animation"] = [
        {"tracks": [{"path": ["nodes", "camera", "translation"], "keys": cam,
                     "interpolation": "LINEAR"}]},
        {"tracks": [{"path": ["nodes", "aim", "translation"], "keys": aim,
                     "interpolation": "LINEAR"}]},
        # Camera-distance absorption: the materials need the eye position, so it
        # rides the same track as the camera.
        {"tracks": [{"path": ["materials", "fish", "inputs", "eye"], "keys": cam,
                     "interpolation": "LINEAR"}]},
        {"tracks": [{"path": ["materials", "seabed", "inputs", "eye"], "keys": cam,
                     "interpolation": "LINEAR"}]},
    ]
    return scene


def write_buffers():
    (SCENE / "state.bin").write_bytes(bytes(16 * N))
    (SCENE / "rotation.bin").write_bytes(struct.pack("<4f", 0, 0, 0, 1) * N)
    (SCENE / "grid.bin").write_bytes(bytes(4 * GRID_COUNT))


def main():
    SCENE.mkdir(parents=True, exist_ok=True)
    write_buffers()
    scene = build_scene()
    path = SCENE / "scene.json"
    path.write_text(json.dumps(scene, indent=1) + "\n")

    print(f"wrote {path}")
    print(f"  fish            : {N:,}")
    print(f"  grid            : {GRID_DIM[0]}x{GRID_DIM[1]}x{GRID_DIM[2]} x4 = {GRID_COUNT:,} u32")
    print(f"  state.bin       : {16 * N / 1e6:.1f} MB")
    print(f"  fish mesh       : {len(scene['buffers']['fish_i']['data']) // 3} tris")
    print(f"  reef mesh       : {len(scene['buffers']['reef_i']['data']) // 3} tris")
    print(f"  sun direction   : {r3(sun_direction())}")


if __name__ == "__main__":
    main()
