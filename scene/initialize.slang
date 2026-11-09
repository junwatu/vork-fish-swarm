// initialize.slang — seed the bait ball once at t0.
//
// Fish start on a loose shell around the roost, already milling: each gets a
// tangential velocity so the ball swirls from the first frame, plus noise.
struct Inputs {};

uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; return x ^ (x >> 16); }
float rnd(uint s) { return float(hash(s) >> 8) / 16777216.; }

float4 face_dir(float3 v) {
    float3 d = normalize(v + float3(1e-5, 0.0, 1e-5));
    float4 q = float4(cross(float3(0, 0, 1), d), 1.0 + d.z);
    float n = length(q);
    return n > 1e-6 ? q / n : float4(0, 0, 0, 1);
}

void compute(ComputeContext c, Inputs i) {
    uint id = c.id.x;
    float a = rnd(id * 7u + 1u + c.seed) * 6.2831853;
    float r = 5.0 + (rnd(id * 7u + 2u + c.seed) - 0.5) * 3.0;        // ball radius ~3.5..6.5 m
    float3 radial = float3(cos(a), 0.0, sin(a));
    float3 tangential = float3(-radial.z, 0.0, radial.x);
    float3 position = float3(radial.x * r,
                             9.0 + (rnd(id * 7u + 3u + c.seed) - 0.5) * 8.0,
                             radial.z * r);
    float speed = 1.5 + rnd(id * 7u + 4u + c.seed) * 1.5;
    float3 velocity = tangential * speed
                    + float3((rnd(id * 7u + 5u + c.seed) - 0.5) * 2.0,
                             (rnd(id * 7u + 6u + c.seed) - 0.5) * 2.0,
                             (rnd(id * 7u + 7u + c.seed) - 0.5) * 2.0);
    float s = 0.5 + rnd(id * 7u + 8u + c.seed) * 0.3;
    p_store(id, position);
    v_store(id, velocity);
    translation_store(id, position);
    rotation_store(id, face_dir(velocity));
    scale_store(id, float3(s, s, s));
}
