// fish.slang — silvery bait-ball fish.
//
// Countershading (dark back, pale belly), a per-fish tone from a hash of world
// position, and a strong specular so the school flashes silver as it rolls.
// Sunk into the water by the same per-channel distance absorption as the floor.
import vork;
struct Inputs {
    float3 back = float3(0.200, 0.320, 0.380);
    float3 belly = float3(0.850, 0.900, 0.920);
    float3 water = float3(0.030, 0.100, 0.128);
    float3 fog_sigma = float3(0.020, 0.010, 0.007);
    float3 eye = float3(0.0, 7.0, 22.0);
    float glint = 1.00;
};
Closure surface(ShadingContext c, Inputs i) {
    float3 p = c.POSITION;
    float up = clamp(c.NORMAL.y * 0.5 + 0.5, 0.0, 1.0);
    float3 col = lerp(i.belly, i.back, smoothstep(0.35, 0.80, up));
    float v = frac(sin(dot(floor(p * 3.0), float3(12.9898, 78.233, 37.719))) * 43758.5453);
    col *= 0.80 + 0.45 * v;

    float d = length(p - i.eye);
    float3 T = exp(-i.fog_sigma * d);
    col = col * T + i.water * (1.0 - T);

    Closure m = {};
    m.base_color = col;
    m.specular_roughness = 0.28;
    m.specular_weight = i.glint;
    return m;
}
