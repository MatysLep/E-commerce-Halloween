// Export the editable vector diagram to a PNG suitable for reports and presentations.
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.join(root, "doc/architecture/architecture-aws-hybride.svg");
const destination = path.join(root, "doc/architecture/architecture-aws-hybride.png");
const result = await sharp(source).flatten({ background: "#ffffff" }).png().toFile(destination);
console.log(`Diagram exported: ${result.width} × ${result.height} px`);
