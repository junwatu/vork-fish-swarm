// place.slang — commit the step and orient each fish.
//
// Copies next -> current, then writes the per-instance translation and a
// rotation that faces the heading with the tail-wag yaw and nod that make a
// school of fish swim, plus a small bank into the turn. Scale is left alone.
struct Inputs {};
uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; return x ^ (x >> 16); }
float rnd(uint s) { return float(hash(s) >> 8) / 16777216.; }

void compute(ComputeContext c, Inputs i) {
    uint id = c.id.x;
    float3 position = next_p_load(id), velocity = next_v_load(id);
    float3 old = v_load(id);
    p_store(id, position);
    v_store(id, velocity);

    float sp = length(velocity);
    float3 d = sp > 1e-3 ? velocity / sp : float3(0, 0, 1);

    // Tail-driven wag: yaw about the local up plus a small nod.
    float phase = rnd(id * 13u + 1u) * 6.2831853;
    float wag = sin(c.time * 7.0 + phase) * 0.30;
    float nod = sin(c.time * 7.0 + phase + 1.2) * 0.10;
    float3 up0 = float3(0.0, 1.0, 0.0);
    float3 rgt = normalize(cross(up0, d) + float3(1e-6, 0.0, 0.0));
    float3 upv = normalize(cross(d, rgt));
    d = normalize(d + rgt * wag + upv * nod);

    float4 q = float4(cross(float3(0, 0, 1), d), 1.0 + d.z);
    float n = length(q);
    q = n > 1e-6 ? q / n : float4(0, 0, 0, 1);

    float3 right = normalize(cross(float3(0, 1, 0), d) + float3(1e-6, 0, 0));
    float bank = clamp(-dot((velocity - old) / c.dt, right) / 90.0, -0.4, 0.4);
    float s = sin(bank * 0.5), cs = cos(bank * 0.5);
    q = float4(q.xyz * cs + float3(q.y, -q.x, q.w) * s, q.w * cs - q.z * s);

    translation_store(id, position);
    rotation_store(id, q);
}
