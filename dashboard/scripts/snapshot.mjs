import { writeFileSync } from "node:fs";
import { collectSnapshot } from "./github-snapshot.mjs";
// Await every source and validate before replacing the previous snapshot.
const data = await collectSnapshot();
writeFileSync(
  new URL("../public/data/snapshot.json", import.meta.url),
  JSON.stringify(data, null, 2) + "\n",
);
console.log(`공개 상태 저장: ${data.generatedAt}`);
