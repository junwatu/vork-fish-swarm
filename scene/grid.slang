// grid.slang — hash each fish into a 64x32x64 spatial grid (0.75 m cells).
//
// Each cell keeps the four smallest hashed keys (a stable, order-independent
// integer insertion network). Domain: x,z in [-24,24], y in [0,24].
struct Inputs {};
uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; return x ^ (x >> 16); }

uint3 cell_of(float3 position) {
    float3 q = (position - float3(-24.0, 0.0, -24.0)) / 0.75;
    return uint3(clamp(floor(q), 0.0, float3(63.0, 31.0, 63.0)));
}
void compute(ComputeContext c, Inputs i) {
    uint id = c.id.x;
    uint3 cell = cell_of(p_load(id));
    uint base = ((cell.z * 32u + cell.y) * 64u + cell.x) * 4u;
    uint key = (hash(id + c.seed) & 0xfff00000u) | id;
    for (uint j = 0; j < 4 && key != 0xffffffffu; j++) {
        uint old = grid_atomic_min(base + j, key);
        key = max(key, old);
    }
}
