// estimate.sustenaut.eu: only past the team sign-in, for whoever holds the role estimate. It goes out as the Pages
// project's _worker.js (.github/workflows/deploy.yml).
// gate.js is a copy of Sustenaut/auth's edge-gate/gate.js: keep it in step with that file.
import { gate } from "./gate.js";
import { failuresNotKept, headersFor } from "./headers.js";

const gated = gate({ role: "estimate", headers: headersFor });

export default { fetch: async (request, env) => failuresNotKept(await gated.fetch(request, env)) };
