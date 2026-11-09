// water.slang — the underwater environment (std/sky's replacement).
//
// There is no participating medium in this release, so the water is painted
// here: a blue-green gradient that brightens toward the surface, a sun glow and
// disk, and a slow caustic shimmer on the up hemisphere. Distance absorption
// that actually tints geometry is done per-material (see fish/seabed).
import vork;
struct Inputs {
    float3 sun_dir = float3(0.24, 0.87, -0.44);
    float3 deep = float3(0.012, 0.045, 0.062);
    float3 shallow = float3(0.100, 0.300, 0.360);
    float3 surface_light = float3(0.600, 0.900, 1.000);
};
float3 environment(EnvironmentContext c, Inputs i) {
    float3 d = normalize(c.direction);
    float up = clamp(d.y, -1.0, 1.0);
    float3 col = lerp(i.deep, i.shallow, smoothstep(-0.35, 0.55, up));
    col = lerp(col, i.surface_light, smoothstep(0.55, 1.0, up));
    // Shimmer: the moving surface band of caustic light seen from below.
    float t = c.time;
    float shimmer = sin(d.x * 9.0 + t * 0.9) * sin(d.z * 7.0 - t * 0.7);
    col += i.surface_light * max(shimmer, 0.0) * 0.06 * smoothstep(0.4, 1.0, up);
    // The sun: a broad glow plus a small bright disk for camera rays.
    float sd = max(dot(d, normalize(i.sun_dir)), 0.0);
    col += i.surface_light * pow(sd, 18.0) * 0.35;
    if (c.camera) col += i.surface_light * pow(sd, 900.0) * 6.0;
    return col;
}
