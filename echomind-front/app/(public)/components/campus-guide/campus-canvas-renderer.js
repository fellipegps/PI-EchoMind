import * as THREE from 'three';

const sunDirection = new THREE.Vector3(-.55, .8, .31).normalize();
const axisA = new THREE.Vector3();
const axisB = new THREE.Vector3();
const normal = new THREE.Vector3();
const shaded = new THREE.Color();

function pack(hex) {
  return (0xff000000 | ((hex & 0xff) << 16) | (hex & 0xff00) | (hex >> 16)) >>> 0;
}

function faceColor(base, a, b, c) {
  normal.crossVectors(axisA.subVectors(b, a), axisB.subVectors(c, a)).normalize();
  const amount = .49 + .16 * (normal.y + 1) / 2 + .48 * Math.max(0, normal.dot(sunDirection));
  return pack(shaded.copy(base).multiplyScalar(amount).getHex());
}

function bakeGeometry(mesh, matrix, instanceColor, triangles) {
  const {geometry} = mesh;
  if (geometry.type === 'PlaneGeometry') return;
  const {position} = geometry.attributes;
  const index = geometry.getIndex();
  const size = index?.count ?? position.count;
  const vertices = Array.from({length: position.count}, (_, i) => new THREE.Vector3()
    .fromBufferAttribute(position, i).applyMatrix4(matrix));
  const surfaces = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  const parts = geometry.groups.length && surfaces.length > 1 ? geometry.groups : [{start: 0, count: size, materialIndex: 0}];
  for (const {start, count, materialIndex} of parts) {
    const base = surfaces[materialIndex].color.clone().multiply(instanceColor);
    for (let i = start; i < start + count; i += 3) {
      const vertex = (j) => vertices[index ? index.getX(i + j) : i + j];
      const a = vertex(0), b = vertex(1), c = vertex(2);
      triangles.push({a, b, c, color: faceColor(base, a, b, c)});
    }
  }
}

export function createCanvasRenderer() {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d', {alpha: false});
  if (!context) throw new Error('Canvas não está disponível.');
  const world = new THREE.Matrix4();
  const instance = new THREE.Matrix4();
  const tint = new THREE.Color();
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const linePoint = new THREE.Vector3();
  const horizon = new THREE.Vector3();
  const triangles = [];
  const overlays = [];
  let displayWidth, displayHeight, width, height, depth, pixels, image;
  let baked = false;

  function bakeScene(scene) {
    scene.updateMatrixWorld(true);
    scene.traverse((mesh) => {
      if (mesh.isLineLoop || mesh.geometry?.type === 'RingGeometry') {
        overlays.push(mesh);
        return;
      }
      if (!mesh.isMesh) return;
      if (!mesh.isInstancedMesh) {
        bakeGeometry(mesh, mesh.matrixWorld, tint.setRGB(1, 1, 1), triangles);
        return;
      }
      for (let i = 0; i < mesh.count; i++) {
        mesh.getMatrixAt(i, instance);
        tint.setRGB(1, 1, 1);
        if (mesh.instanceColor) mesh.getColorAt(i, tint);
        bakeGeometry(mesh, world.multiplyMatrices(mesh.matrixWorld, instance), tint, triangles);
      }
    });
    baked = true;
  }

  function project(vector, camera) {
    vector.project(camera);
    vector.x = (vector.x + 1) * width / 2;
    vector.y = (1 - vector.y) * height / 2;
    return vector;
  }

  function rasterize({a: p0, b: p1, c: p2, color}, camera) {
    project(a.copy(p0), camera);
    project(b.copy(p1), camera);
    project(c.copy(p2), camera);
    if (a.z >= 1 || b.z >= 1 || c.z >= 1 || a.z < -1 || b.z < -1 || c.z < -1) return;
    const abX = b.x - a.x, abY = b.y - a.y;
    const acX = c.x - a.x, acY = c.y - a.y;
    const area = abX * acY - acX * abY;
    if (area >= -.06) return;

    const left = Math.max(0, Math.floor(Math.min(a.x, b.x, c.x)));
    const right = Math.min(width - 1, Math.ceil(Math.max(a.x, b.x, c.x)));
    const top = Math.max(0, Math.floor(Math.min(a.y, b.y, c.y)));
    const bottom = Math.min(height - 1, Math.ceil(Math.max(a.y, b.y, c.y)));
    const stepU = acY / area, stepV = -abY / area;
    const zAB = b.z - a.z, zAC = c.z - a.z;
    for (let y = top; y <= bottom; y++) {
      const offsetY = y + .5 - a.y;
      const offsetX = left + .5 - a.x;
      let u = (offsetX * acY - offsetY * acX) / area;
      let v = (abX * offsetY - abY * offsetX) / area;
      let offset = y * width + left;
      for (let x = left; x <= right; x++, offset++, u += stepU, v += stepV) {
        if (u < 0 || v < 0 || u + v > 1) continue;
        const z = a.z + u * zAB + v * zAC;
        if (z >= depth[offset]) continue;
        depth[offset] = z;
        pixels[offset] = color;
      }
    }
  }

  function drawOverlay(overlay, camera) {
    if (!overlay.visible) return;
    overlay.updateWorldMatrix(true, false);
    const positions = overlay.geometry.attributes.position;
    const isRing = overlay.geometry.type === 'RingGeometry';
    const count = isRing ? positions.count / 2 - 1 : positions.count;
    context.beginPath();
    for (let i = 0; i < count; i++) {
      project(linePoint.fromBufferAttribute(positions, i).applyMatrix4(overlay.matrixWorld), camera);
      if (linePoint.z < -1 || linePoint.z >= 1) return;
      if (!i) context.moveTo(linePoint.x, linePoint.y);
      else context.lineTo(linePoint.x, linePoint.y);
    }
    context.closePath();
    context.strokeStyle = '#' + overlay.material.color.getHexString();
    context.lineWidth = 2;
    context.stroke();
  }

  function resizeRaster(moving) {
    const density = devicePixelRatio || 1;
    const pixelsLimit = moving ? 680_000 : 1_900_000;
    const desiredScale = moving ? Math.min(density, 1.5) : Math.min(Math.max(density, 1.5), 2);
    const scale = Math.min(desiredScale, Math.sqrt(pixelsLimit / (displayWidth * displayHeight)));
    const nextWidth = Math.max(1, Math.round(displayWidth * scale));
    const nextHeight = Math.max(1, Math.round(displayHeight * scale));
    if (width === nextWidth && height === nextHeight) return;
    width = canvas.width = nextWidth;
    height = canvas.height = nextHeight;
    image = context.createImageData(width, height);
    pixels = new Uint32Array(image.data.buffer);
    depth = new Float32Array(width * height);
  }

  return {
    domElement: canvas,
    setSize(w, h) {
      displayWidth = w;
      displayHeight = h;
    },
    render(scene, camera, moving = false) {
      resizeRaster(moving);
      if (!baked) bakeScene(scene);
      camera.getWorldDirection(horizon).setY(0).normalize().multiplyScalar(camera.far / 2).add(camera.position);
      project(horizon, camera);
      const sky = THREE.MathUtils.clamp(Math.round(horizon.y), 0, height) * width;
      pixels.fill(pack(0xbacbbf), 0, sky);
      pixels.fill(pack(0xaab69d), sky);
      depth.fill(Infinity);
      for (const triangle of triangles) rasterize(triangle, camera);
      context.putImageData(image, 0, 0);
      for (const overlay of overlays) drawOverlay(overlay, camera);
    },
  };
}
