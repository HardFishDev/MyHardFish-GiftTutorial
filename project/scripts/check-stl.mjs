import fs from 'node:fs/promises';

for (const id of ['nanyu', 'dbh']) {
  const data = await fs.readFile(new URL(`${id}-raw-150mm.stl`, import.meta.url));
  const triangleCount = data.readUInt32LE(80);
  const edges = new Map();
  const vertexKey = offset => [0, 4, 8].map(delta => Math.round(data.readFloatLE(offset + delta) * 10000)).join(',');
  for (let triangle = 0; triangle < triangleCount; triangle++) {
    const offset = 84 + triangle * 50 + 12;
    const vertices = [0, 12, 24].map(delta => vertexKey(offset + delta));
    for (let side = 0; side < 3; side++) {
      const pair = [vertices[side], vertices[(side + 1) % 3]].sort();
      if (pair[0] === pair[1]) continue;
      const key = pair.join('|');
      edges.set(key, (edges.get(key) ?? 0) + 1);
    }
  }
  const boundaryEdges = [...edges.values()].filter(count => count === 1).length;
  const nonManifoldEdges = [...edges.values()].filter(count => count > 2).length;
  console.log(JSON.stringify({ id, triangleCount, boundaryEdges, nonManifoldEdges, toleranceMm: 0.0001 }));
}
