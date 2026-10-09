import { build } from '../MyHardFish-web/node_modules/esbuild/lib/main.js';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const output = path.dirname(fileURLToPath(import.meta.url));
const project = path.resolve(output, '../MyHardFish-web');
globalThis.window = {};
// STL stores geometry only. Texture painting has no effect on the mesh.
globalThis.document = { createElement: () => ({ width: 1, height: 1,
  getContext: () => new Proxy({}, { get: (_target, key) => {
    if (key === 'createImageData') return (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) });
    if (key === 'createRadialGradient' || key === 'createLinearGradient') return () => ({ addColorStop() {} });
    if (key === 'measureText') return () => ({ width: 100 });
    return () => {};
  }, set: () => true }) }) };
const bundle = await build({ stdin: { contents: `export { NanyuCharacter } from './src/character.ts'; export { createDbhCharacter } from './src/dbh-character.ts'; export * as THREE from 'three';`, resolveDir: project },
  bundle: true, format: 'esm', platform: 'node', write: false,
  plugins: [{ name: 'local-three', setup(builder) { builder.onResolve({ filter: /^three(?:\/|$)/ }, args => ({ path: args.path === 'three'
    ? path.join(project, 'node_modules/three/build/three.module.js')
    : path.join(project, 'node_modules/three', args.path.replace(/^three\/addons\//, 'examples/jsm/').replace(/^three\//, '')) })); } }] });
await fs.writeFile(path.join(output, 'models.bundle.mjs'), bundle.outputFiles[0].contents);
const { NanyuCharacter, createDbhCharacter, THREE } = await import('./models.bundle.mjs');
const models = [['nanyu', new NanyuCharacter()], ['dbh', createDbhCharacter()]];
const report = {};
for (const [id, model] of models) {
  model.root.updateMatrixWorld(true);
  model.root.traverse(node => { if (node.isSkinnedMesh) node.skeleton.update(); });
  const meshes = [], box = new THREE.Box3();
  model.root.traverseVisible(node => {
    if (!node.isMesh || (node.geometry.type === 'PlaneGeometry' && node.material.transparent)) return;
    const positions = node.geometry.attributes.position;
    const points = Array.from({ length: positions.count }, (_, i) => {
      const p = node.getVertexPosition(i, new THREE.Vector3()).applyMatrix4(node.matrixWorld);
      if (![p.x, p.y, p.z].every(Number.isFinite)) throw new Error(`${id}: invalid vertex`);
      box.expandByPoint(p); return p;
    });
    const indices = node.geometry.index ? Array.from(node.geometry.index.array) : points.map((_, i) => i);
    meshes.push({ name: node.name || node.userData.qaRole || `mesh-${meshes.length}`, points, indices });
  });
  const scale = 150 / (box.max.y - box.min.y);
  const centerX = (box.min.x + box.max.x) / 2, centerZ = (box.min.z + box.max.z) / 2;
  const triangles = [], inventory = [];
  for (const mesh of meshes) {
    const mapped = mesh.points.map(p => new THREE.Vector3((p.x - centerX) * scale, -(p.z - centerZ) * scale, (p.y - box.min.y) * scale));
    const start = triangles.length;
    for (let i = 0; i < mesh.indices.length; i += 3) {
      const tri = mesh.indices.slice(i, i + 3).map(index => mapped[index]);
      const normal = new THREE.Vector3().crossVectors(new THREE.Vector3().subVectors(tri[1], tri[0]), new THREE.Vector3().subVectors(tri[2], tri[0]));
      if (normal.lengthSq() < 1e-14) continue;
      triangles.push({ vertices: tri, normal: normal.normalize() });
    }
    inventory.push({ name: mesh.name, firstTriangle: start, triangles: triangles.length - start });
  }
  const binary = Buffer.alloc(84 + triangles.length * 50);
  binary.write(`MyHardFish ${id} | mm | Z up | geometry extraction`); binary.writeUInt32LE(triangles.length, 80);
  triangles.forEach((tri, i) => {
    const values = [...tri.normal.toArray(), ...tri.vertices.flatMap(p => p.toArray())];
    values.forEach((value, j) => binary.writeFloatLE(value, 84 + i * 50 + j * 4));
  });
  await fs.writeFile(path.join(output, `${id}-raw-150mm.stl`), binary);
  report[id] = { file: `${id}-raw-150mm.stl`, units: 'mm', pose: 'initial idle pose, baked skinning and morphs',
    size: [(box.max.x - box.min.x) * scale, (box.max.z - box.min.z) * scale, 150],
    meshes: inventory, triangles: triangles.length, textures: 'not included in STL', printable: 'not yet validated' };
  model.dispose();
}
await fs.writeFile(path.join(output, 'extraction-report.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(Object.fromEntries(Object.entries(report).map(([id, item]) => [id, { size: item.size, triangles: item.triangles, meshes: item.meshes.length }]))));
