// seabed.slang — the reef floor the bait ball mills over.
//
// A sandy, lightly dune-shaped field animated by moving caustics (the bright
// refracted cells of light from the surface), then sunk into the water by
// per-channel distance absorption: red goes first, then green, leaving blue.
import vork;
struct Inputs {
    float3 sand_low = float3(0.055, 0.062, 0.050);
    float3 sand_high = float3(0.135, 0.140, 0.110);
    float3 caustic_color = float3(0.45, 0.72, 0.62);
    float3 water = float3(0.030, 0.100, 0.128);
    float3 fog_sigma = float3(0.045, 0.026, 0.020);   // per metre, red absorbs fastest
    float3 eye = float3(0.0, 7.0, 22.0);
    float caustic_scale = 1.60;
    float caustic_speed = 0.55;
    float caustic_amount = 0.35;
};
float caustic(float2 p, float t) {
    float2 q = p;
    float v = 0.0;
    for (uint k = 0; k < 3u; k++) {
        q = p + float2(sin(q.y * 1.3 + t) + cos(q.x * 1.1 - t * 0.8),
                       cos(q.x * 1.2 - t) + sin(q.y * 1.4 + t * 0.7)) * 0.6;
        v += 1.0 - abs(sin(q.x * 0.9) * sin(q.y * 0.9));
    }
    return pow(clamp(v / 3.0, 0.0, 1.0), 3.0);
}
Closure surface(ShadingContext c, Inputs i) {
    float3 p = c.POSITION;
    float dune = 0.5 + 0.5 * sin(p.x * 0.09) * sin(p.z * 0.07);
    float3 col = lerp(i.sand_low, i.sand_high, 0.30 + 0.70 * dune);

    float caus = caustic(p.xz * i.caustic_scale, c.time * i.caustic_speed);
    float facing = clamp(c.NORMAL.y, 0.0, 1.0);
    col += i.caustic_color * caus * facing * i.caustic_amount;

    float d = length(p - i.eye);
    float3 T = exp(-i.fog_sigma * d);
    col = col * T + i.water * (1.0 - T);

    Closure m = {};
    m.base_color = col;
    m.specular_roughness = 0.92;
    m.specular_weight = 0.06;
    return m;
}
