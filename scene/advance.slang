// advance.slang — one schooling step for the bait ball.
//
// 12-nearest-neighbour schooling (cohesion / alignment / separation) layered on
// the driver that keeps a bait ball a compact, milling body: a centring spring
// plus a tangential drive, an altitude spring, and drag. A predator (barracuda)
// slices through and the ball opens a hole around it.
struct Inputs {
    float cohesion = 0.30;
    float alignment = 1.20;
    float separation = 14.00;
    float centre_pull = 0.60;
    float wheel_drive = 0.90;
};
int3 cell_of(float3 position) {
    float3 q = (position - float3(-24.0, 0.0, -24.0)) / 0.75;
    return int3(clamp(floor(q), 0.0, float3(63.0, 31.0, 63.0)));
}
void compute(ComputeContext c, Inputs i) {
    uint id = c.id.x;
    float3 position = p_load(id), velocity = v_load(id);
    int3 cell = cell_of(position);

    const uint K = 12u;
    float distances[12]; uint neighbours[12];
    for (uint k = 0; k < K; k++) { distances[k] = 1e20; neighbours[k] = id; }
    for (int z = -1; z <= 1; z++) for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
        int3 other = cell + int3(x, y, z);
        if (any(other < 0) || any(other >= int3(64, 32, 64))) continue;
        uint base = ((other.z * 32 + other.y) * 64 + other.x) * 4;
        for (uint j = 0; j < 4; j++) {
            uint key = grid_load(base + j); if (key == 0xffffffffu) break;
            uint nb = key & 0xfffffu; if (nb == id) continue;
            float3 delta = p_load(nb) - position; float d2 = dot(delta, delta);
            if (d2 >= distances[K - 1u]) continue;
            for (uint k = 0; k < K; k++) if (d2 < distances[k]) {
                float od = distances[k]; uint opn = neighbours[k];
                distances[k] = d2; neighbours[k] = nb; d2 = od; nb = opn;
            }
        }
    }

    float3 centre = 0, heading = 0, repel = 0; uint count = 0;
    for (uint k = 0; k < K; k++) if (neighbours[k] != id) {
        float3 delta = p_load(neighbours[k]) - position;
        centre += delta; heading += v_load(neighbours[k]);
        repel -= delta / max(dot(delta, delta), 1.0); count++;
    }

    // Fixed roost: the school mills around one point, so the camera can hold it
    // centred while it swirls.
    float3 roost = float3(0.0, 9.0, 0.0);
    float3 rel = position - roost; rel.y = 0.0;
    float rr = length(rel);
    float3 radial = rr > 1e-3 ? rel / rr : float3(1.0, 0.0, 0.0);
    float3 tangential = float3(-radial.z, 0.0, radial.x);

    float3 force = (roost - position) * i.centre_pull
                 + tangential * i.wheel_drive
                 + float3(0.0, (9.0 - position.y) * 0.90, 0.0)
                 - velocity * 1.00;
    if (count > 0)
        force += i.cohesion * centre / count
               + i.alignment * (heading / count - velocity)
               + i.separation * repel / count;

    // Soft walls: stay off the seabed and below the surface, inside the reef.
    if (rr > 12.0) force -= radial * (rr - 12.0) * 3.0;
    if (position.y < 2.5) force.y += (2.5 - position.y) * 3.0;
    if (position.y > 16.0) force.y -= (position.y - 16.0) * 3.0;

    float al = length(force);
    force *= min(1.0, 10.0 / max(al, 1e-4));
    velocity += force * c.dt;
    float sp = length(velocity);
    if (sp > 0.0) velocity *= clamp(sp, 1.0, 5.0) / sp;

    next_v_store(id, velocity);
    next_p_store(id, position + velocity * c.dt);
}
