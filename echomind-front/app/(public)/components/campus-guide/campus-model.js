import * as THREE from 'three';

const anapolisOrigin = [-48.944138, -16.294593];
const latitudeMeters = 111319.49;

const profiles = {
  biblioteca: {levels: 3, wall: '#e7dcc3', roof: '#c5bda8', accent: '#965c49', windows: 'ribbon'},
  'bloco-a': {levels: 4, wall: '#dcded0', roof: '#788c7e', accent: '#597766', windows: 'vertical'},
  'bloco-c': {levels: 4, wall: '#ead8bc', roof: '#bcb5a1', accent: '#a67e4b', windows: 'framed'},
  ginasio: {levels: 1, wall: '#cbb561', roof: '#aab3b2', accent: '#667681', windows: 'hall'},
};
const contextProfile = {wall: '#bfc0ae', roof: '#a4ab9c', accent: '#8d9c90'};
const campusProfile = {wall: '#e1d8c3', roof: '#b5b9ad', accent: '#8b7960', windows: 'framed'};

function campusProjection(origin) {
  const longitudeMeters = latitudeMeters * Math.cos(THREE.MathUtils.degToRad(origin[1]));
  return ([lng, lat], elevation = 0) =>
    new THREE.Vector3((lng - origin[0]) * longitudeMeters, elevation, (origin[1] - lat) * latitudeMeters);
}

function material(color, properties = {}) {
  return new THREE.MeshStandardMaterial({color, roughness: .84, ...properties});
}

function shapeOf(points) {
  return new THREE.Shape(points.map(({x, z}) => new THREE.Vector2(x, -z)));
}

function polygonMesh(points, surface, y, depth = 0, walls = surface) {
  const shape = shapeOf(points);
  const geometry = depth
    ? new THREE.ExtrudeGeometry(shape, {depth, bevelEnabled: false})
    : new THREE.ShapeGeometry(shape);
  geometry.rotateX(-Math.PI / 2);
  const mesh = new THREE.Mesh(geometry, depth ? [surface, walls] : surface);
  mesh.position.y = y;
  mesh.receiveShadow = true;
  mesh.castShadow = depth > 0;
  return mesh;
}

function addGymRoof(group, points, base, top, roofMaterial, wallMaterial) {
  const longest = points.reduce((index, point, i) => point.distanceToSquared(points[(i + 1) % 4]) >
    points[index].distanceToSquared(points[(index + 1) % 4]) ? i : index, 0);
  const [a, b, c, d] = points.map((_, i) => points[(longest + i) % 4].clone().setY(base));
  const first = a.clone().lerp(d, .5).setY(top);
  const second = b.clone().lerp(c, .5).setY(top);
  const face = (corners, expectedNormal, surface) => {
    const positions = [];
    for (let i = 1; i < corners.length - 1; i++) {
      const [p0, p1, p2] = [corners[0], corners[i], corners[i + 1]];
      const normal = p1.clone().sub(p0).cross(p2.clone().sub(p0));
      const triangle = normal.dot(expectedNormal) > 0 ? [p0, p1, p2] : [p0, p2, p1];
      positions.push(...triangle.flatMap(({x, y, z}) => [x, y, z]));
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, surface);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    group.add(mesh);
  };
  const up = new THREE.Vector3(0, 1, 0);
  face([a, b, second, first], up, roofMaterial);
  face([first, second, c, d], up, roofMaterial);
  face([a, first, d], first.clone().sub(second), wallMaterial);
  face([b, c, second], second.clone().sub(first), wallMaterial);
}

function boxBatches(group) {
  const batches = new Map();
  const transform = new THREE.Object3D();
  return {
    add(surface, width, height, depth, x, y, z, yaw = 0) {
      const matrices = batches.get(surface) ?? [];
      if (!batches.has(surface)) batches.set(surface, matrices);
      transform.position.set(x, y, z);
      transform.rotation.set(0, yaw, 0);
      transform.scale.set(width, height, depth);
      transform.updateMatrix();
      matrices.push(transform.matrix.clone());
    },
    flush() {
      const geometry = new THREE.BoxGeometry();
      for (const [surface, matrices] of batches) {
        const mesh = new THREE.InstancedMesh(geometry, surface, matrices.length);
        matrices.forEach((matrix, index) => mesh.setMatrixAt(index, matrix));
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        group.add(mesh);
      }
    },
  };
}

function edgesOf(points) {
  const winding = points.reduce((area, point, index) => {
    const next = points[(index + 1) % points.length];
    return area + point.x * next.z - next.x * point.z;
  }, 0);
  return points.map((point, index) => {
    const next = points[(index + 1) % points.length];
    const [start, end] = winding > 0 ? [next, point] : [point, next];
    const along = end.clone().sub(start);
    const length = along.length();
    along.divideScalar(length);
    const outward = new THREE.Vector3(-along.z, 0, along.x);
    return {start, along, outward, length, yaw: -Math.atan2(along.z, along.x)};
  });
}

function subdivisionEdgeKey(osmWayId, ring, index) {
  const endpoints = [ring[index].join(','), ring[index + 1].join(',')].sort();
  return `${osmWayId}:${endpoints.join('|')}`;
}

function sharedSubdivisionEdges(features) {
  const seen = new Set();
  const shared = new Set();
  for (const {geometry, properties} of features) {
    if (properties.geometryStatus !== 'subdivision') continue;
    const ring = geometry.coordinates[0];
    for (let index = 0; index < ring.length - 1; index++) {
      const key = subdivisionEdgeKey(properties.osmWayId, ring, index);
      if (seen.has(key)) shared.add(key);
      seen.add(key);
    }
  }
  return shared;
}

function atEdge(edge, along, outward = 0) {
  return edge.start.clone().addScaledVector(edge.along, along).addScaledVector(edge.outward, outward);
}

function accessEdge(edges, point) {
  if (!point) return null;
  let closest = null;
  for (const edge of edges) {
    if (edge.length < 6) continue;
    const offset = point.clone().sub(edge.start).dot(edge.along);
    const along = THREE.MathUtils.clamp(offset, 2.6, edge.length - 2.6);
    const distance = atEdge(edge, along).distanceToSquared(point);
    if (!closest || distance < closest.distance) closest = {edge, along, distance};
  }
  return closest;
}

function buildArchitecture(group, {points, edges, profile, height, access, roofDetails}) {
  const details = boxBatches(group);
  const frames = material('#293c39');
  const glass = material('#547878', {roughness: .25, metalness: .17});
  const darkGlass = material('#365958', {roughness: .29, metalness: .1});
  const warmGlass = material('#a38b67', {roughness: .33, metalness: .05});
  const accent = material(profile.accent);
  const coping = material(profile.wall);
  const metal = material('#a9b1a7');
  const entrance = accessEdge(edges, access);
  const hall = profile.windows === 'hall';
  const levels = profile.levels ?? THREE.MathUtils.clamp(Math.round(height / 3.7), 1, 5);
  const floorHeight = (height - .85) / levels;
  const place = (edge, along, y, out, w, h, d, surface) => {
    const {x, z} = atEdge(edge, along, out);
    details.add(surface, w, h, d, x, y, z, edge.yaw);
  };

  for (const [side, edge] of edges.entries()) {
    const {length} = edge;
    if (!hall) place(edge, length / 2, height + .45, .03, length, .9, .38, coping);
    place(edge, length / 2, .34, .05, length, .68, .32, accent);
    if (length < 3.5) continue;

    const bayWidth = hall ? 11 : profile.windows === 'framed' ? 4.2 : 5.2;
    const bays = Math.max(1, Math.round(length / bayWidth));
    const spacing = length / bays;
    const span = spacing * (profile.windows === 'ribbon' ? .88 : profile.windows === 'vertical' ? .56 : .67);
    for (let level = 0; level < levels; level++) {
      const y = .72 + (level + (hall ? .76 : .5)) * floorHeight;
      if (level && profile.windows !== 'vertical') {
        place(edge, length / 2, .57 + level * floorHeight, .12, length, .19, .37, coping);
      }
      for (let bay = 0; bay < bays; bay++) {
        const along = (bay + .5) * spacing;
        if (!level && entrance?.edge === edge && Math.abs(along - entrance.along) < 2.8 + span / 2) continue;
        const opening = floorHeight * (hall ? .16 : profile.windows === 'vertical' ? .69 : .53);
        const shade = (side * 3 + level * 7 + bay) % 13;
        place(edge, along, y, .10, span + .22, opening + .19, .28, frames);
        place(edge, along, y, .27, span, opening, .10, shade === 5 ? warmGlass : shade < 4 ? darkGlass : glass);
        place(edge, along, y, .34, .09, opening, .09, frames);
        place(edge, along, y - opening / 2 - .09, .24, span + .42, .14, .39, coping);
      }
    }
    for (let bay = 1; bay < bays; bay += profile.windows === 'ribbon' ? 2 : 3) {
      place(edge, bay * spacing, height / 2, .23, profile.windows === 'vertical' ? .72 : .38, height, .56, accent);
    }
  }

  if (entrance) {
    const {edge, along} = entrance;
    place(edge, along, 1.62, .14, 4.7, 3.24, .52, frames);
    place(edge, along, 1.57, .48, 4.25, 2.98, .18, darkGlass);
    place(edge, along, 1.57, .62, .16, 2.98, .12, metal);
    place(edge, along, 3.45, 1.42, 6.4, .34, 3.1, accent);
    place(edge, along, .12, 1.75, 6.6, .24, 3.75, coping);
    for (const direction of [-1, 1]) {
      place(edge, along + direction * 2.74, 1.71, 2.72, .32, 3.17, .36, frames);
    }
  }

  if (roofDetails && !hall) {
    const center = points.reduce((total, point) => total.add(point), new THREE.Vector3()).divideScalar(points.length);
    details.add(coping, 5.4, 1.65, 4.7, center.x + 2, height + .82, center.z - 2);
    details.add(metal, 2.9, .62, 1.7, center.x - 3, height + .31, center.z + 1.7);
    details.add(frames, 2.6, .21, 1.4, center.x - 3, height + .70, center.z + 1.7);
  }
  details.flush();

  return entrance && {outward: entrance.edge.outward};
}

function addGround(scene, context, campusPosition) {
  const terrain = new THREE.Group();
  terrain.userData.ground = true;
  scene.add(terrain);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2100, 2100), material('#aab69d'));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -.15;
  ground.receiveShadow = true;
  terrain.add(ground);
  const areas = {
    campus: {color: '#c5c8ad', y: -.08},
    green: {color: '#8f9e78', y: -.03},
    court: {color: '#798f79', y: .012},
    paving: {color: '#e0d5bc', y: .015},
    parking: {color: '#9ca39a', y: .02},
  };
  const lines = {
    avenue: {color: '#747d73', width: 9, y: .04},
    road: {color: '#a1a494', width: 4, y: .07},
    walk: {color: '#e1d6bd', width: 2.5, y: .09},
    track: {color: '#ac795e', width: 5, y: .095},
    'parking-line': {color: '#dcdcc9', width: .13, y: .11},
  };
  const surfaces = new Map(Object.entries({...areas, ...lines}).map(([kind, {color}]) => [kind, material(color)]));
  const roads = boxBatches(terrain);
  for (const {geometry, properties: {kind}} of context.features) {
    if (areas[kind]) {
      terrain.add(polygonMesh(geometry.coordinates[0].map((point) => campusPosition(point)), surfaces.get(kind), areas[kind].y));
    }
    if (!lines[kind]) continue;
    const {width, y} = lines[kind];
    const points = geometry.coordinates.map((point) => campusPosition(point));
    for (let i = 1; i < points.length; i++) {
      const [a, b] = [points[i - 1], points[i]];
      const yaw = -Math.atan2(b.z - a.z, b.x - a.x);
      roads.add(surfaces.get(kind), a.distanceTo(b) + width / 3, .025, width, (a.x + b.x) / 2, y, (a.z + b.z) / 2, yaw);
    }
  }
  roads.flush();
}

function addTrees(scene, context, campusPosition) {
  const trees = context.features.filter(({properties}) => properties.kind === 'tree');
  if (!trees.length) return;
  const trunk = new THREE.InstancedMesh(new THREE.CylinderGeometry(.14, .22, 1, 6), material('#645c46'), trees.length);
  const foliage = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1), material('#ffffff'), trees.length * 2);
  const shades = ['#5b7755', '#718863', '#7f9264'].map((color) => new THREE.Color(color));
  const dummy = new THREE.Object3D();
  trees.forEach(({geometry, properties}, i) => {
    const ring = geometry.coordinates[0].slice(0, -1);
    const center = ring.reduce((sum, coordinates) => sum.add(campusPosition(coordinates)), new THREE.Vector3()).divideScalar(ring.length);
    const height = properties.heightMeters;
    dummy.position.set(center.x, height * .25, center.z);
    dummy.scale.set(1, height * .5, 1);
    dummy.updateMatrix();
    trunk.setMatrixAt(i, dummy.matrix);
    for (const crown of [0, 1]) {
      dummy.position.set(center.x + (crown - .5) * height * .33, height * (.7 + crown * .15), center.z);
      dummy.rotation.y = i * .7;
      dummy.scale.set(height * .46, height * .46, height * .41).multiplyScalar(crown ? .74 : 1);
      dummy.updateMatrix();
      foliage.setMatrixAt(i * 2 + crown, dummy.matrix);
      foliage.setColorAt(i * 2 + crown, shades[(properties.shade + crown) % shades.length]);
    }
  });
  foliage.castShadow = true;
  foliage.receiveShadow = true;
  scene.add(trunk, foliage);
}

export function createCampusModel({buildings, context, destinations, origin}) {
  const campusPosition = campusProjection(origin ?? anapolisOrigin);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#b9c7b6');
  scene.fog = new THREE.FogExp2('#b9c7b6', .0016);
  scene.add(new THREE.HemisphereLight('#e4f4ff', '#9c896b', 2.1));
  const sun = new THREE.DirectionalLight('#fff1da', 2.7);
  sun.position.set(-125, 180, 70);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -370;
  sun.shadow.camera.right = 370;
  sun.shadow.camera.top = 370;
  sun.shadow.camera.bottom = -370;
  sun.shadow.camera.far = 650;
  sun.shadow.normalBias = .23;
  sun.shadow.bias = -.00028;
  scene.add(sun);

  addGround(scene, context, campusPosition);
  const models = new Map();
  const pickMeshes = [];
  const destinationsById = new Map(destinations.map((destination) => [destination.id, destination]));
  const sharedEdges = sharedSubdivisionEdges(buildings.features);
  for (const {id, geometry, properties} of buildings.features) {
    const ring = geometry.coordinates[0];
    const points = ring.slice(0, -1).map((point) => campusPosition(point));
    const {heightMeters: height, kind} = properties;
    const destination = destinationsById.get(id);
    const profile = (!origin ? profiles[id] : undefined) ?? (destination ? campusProfile : contextProfile);
    const access = destination?.entry.coordinates ? campusPosition(destination.entry.coordinates) : null;
    const approach = destination?.approachCoordinates ? campusPosition(destination.approachCoordinates) : access;
    const base = kind === 'bridge' ? 3 : .11;
    const group = new THREE.Group();
    group.name = destination?.name ?? id;
    const gymRoof = !origin && id === 'ginasio';
    const wallHeight = gymRoof ? height - 6 : height;
    const roofMaterial = material(profile.roof);
    const wallMaterial = material(profile.wall);
    const body = polygonMesh(points, roofMaterial, base, wallHeight - base, wallMaterial);
    group.add(body);
    if (gymRoof) addGymRoof(group, points, wallHeight, height, roofMaterial, wallMaterial);
    scene.add(group);
    if (!destination) continue;
    const isSubdivision = properties.geometryStatus === 'subdivision';
    const edges = edgesOf(points).filter((_, index) =>
      !isSubdivision || !sharedEdges.has(subdivisionEdgeKey(properties.osmWayId, ring, index)));
    const entrance = buildArchitecture(group, {points, edges, profile, height: wallHeight, access: approach, roofDetails: !isSubdivision});
    const outline = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(points.map(({x, z}) => new THREE.Vector3(x, height + 1.18, z))),
      new THREE.LineBasicMaterial(),
    );
    outline.visible = false;
    group.add(outline);
    body.userData.destinationId = id;
    pickMeshes.push(body);
    models.set(id, {body, outline, entrance, height, access});
  }
  addTrees(scene, context, campusPosition);

  const accessRing = new THREE.Mesh(new THREE.RingGeometry(1.95, 2.3, 32), new THREE.MeshBasicMaterial({
    side: THREE.DoubleSide, depthWrite: false,
  }));
  accessRing.rotation.x = -Math.PI / 2;
  accessRing.visible = false;
  scene.add(accessRing);
  scene.updateMatrixWorld(true);
  return {scene, models, pickMeshes, accessRing, campusPosition};
}
