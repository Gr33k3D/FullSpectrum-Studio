import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const resources = resolve(here, "../src-tauri/resources");

await mkdir(resources, { recursive: true });

for (const filename of ["fullspectrum_engine.py", "bambu_mixer_model.py"]) {
  await copyFile(resolve(repoRoot, filename), resolve(resources, filename));
}

console.log(`Synced FullSpectrum engine resources to ${resources}`);
