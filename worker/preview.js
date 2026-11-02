// The site with its headers and no sign-in, for the checks in .github/workflows/deploy.yml, which ask for pages in
// a browser under wrangler before the gate replaces this. It never goes out.
import { failuresNotKept, headersFor } from "./headers.js";

export default {
  async fetch(request, env) {
    const asset = await env.ASSETS.fetch(request);
    const response = new Response(asset.body, asset);
    for (const [name, value] of Object.entries(headersFor(new URL(request.url).pathname))) response.headers.set(name, value);
    return failuresNotKept(response);
  },
};
