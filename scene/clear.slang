// clear.slang — empty the neighbour grid before each rebuild.
struct Inputs {};
void compute(ComputeContext c, Inputs i) { grid_store(c.id.x, 0xffffffffu); }
