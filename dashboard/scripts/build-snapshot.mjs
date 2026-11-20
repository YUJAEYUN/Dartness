import { refreshOnBuild } from "./github-snapshot.mjs";
// Vercel has no GitHub CLI or token requirement. CI remains offline and reproducible.
if (refreshOnBuild(process.env)) await import("./snapshot.mjs");
