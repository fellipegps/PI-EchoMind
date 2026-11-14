import {positionMarkers} from './map-markers.js';

const tileSize = 256;
const minimumZoom = 15;
const maximumZoom = 21;
const maximumLatitude = 85.05112878;
const maximumImageryZoom = 19;
const overviewImageryZoom = 16;
const minimumImageryZoom = 14;
const tileCacheLimit = 96;
const svgNamespace = 'http://www.w3.org/2000/svg';
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function mercator([longitude, latitude]) {
  const clampedLatitude = clamp(latitude, -maximumLatitude, maximumLatitude);
  return {x: (longitude + 180) / 360, y: (1 - Math.asinh(Math.tan(clampedLatitude * Math.PI / 180)) / Math.PI) / 2};
}

function extent(points) {
  const xs = points.map(({x}) => x);
  const ys = points.map(({y}) => y);
  return {left: Math.min(...xs), right: Math.max(...xs), top: Math.min(...ys), bottom: Math.max(...ys)};
}

export function createSatelliteMap({element, buildings, markers, onSelect, onStatus, tiles: imageryTiles}) {
  const imagery = document.createElement('div');
  imagery.className = 'satellite-imagery';
  imagery.setAttribute('aria-hidden', 'true');
  const outlines = document.createElementNS(svgNamespace, 'svg');
  outlines.classList.add('satellite-outlines');
  outlines.setAttribute('aria-hidden', 'true');
  const footprints = buildings.features.filter(({properties}) => properties.kind === 'destination').map(({id, geometry}) => {
    const outline = document.createElementNS(svgNamespace, 'polygon');
    outline.addEventListener('click', () => onSelect(id));
    outlines.append(outline);
    return {id, outline, ring: geometry.coordinates[0].map(mercator)};
  });
  element.append(imagery, outlines);

  const campus = extent(footprints.flatMap(({ring}) => ring));
  const panLimits = extent([mercator([-48.947, -16.299]), mercator([-48.940, -16.289])]);
  const tiles = new Map();
  let center, selected, zoom, frame;
  let destroyed = false;

  const scale = () => tileSize * 2 ** zoom;
  function queueDraw() {
    if (!destroyed && !element.hidden && !frame) frame = requestAnimationFrame(draw);
  }

  function requestTile(level, row, column) {
    const image = document.createElement('img');
    const tile = {image, level, row, column, state: 'pending'};
    image.alt = '';
    image.draggable = false;
    image.addEventListener('load', () => { tile.state = 'loaded'; queueDraw(); });
    image.addEventListener('error', () => { tile.state = 'failed'; queueDraw(); });
    const columns = 2 ** level;
    const wrappedColumn = (column % columns + columns) % columns;
    image.referrerPolicy = 'strict-origin';
    image.src = imageryTiles.url.replaceAll('{z}', level).replaceAll('{x}', wrappedColumn).replaceAll('{y}', row);
    return tile;
  }

  function findImagery(level, row, column, used) {
    let pending = false;
    // Reuse a loaded parent while waiting for detail, or fetch the nearest parent after a miss.
    for (let sourceLevel = level; sourceLevel >= minimumImageryZoom; sourceLevel--) {
      const divisor = 2 ** (level - sourceLevel);
      const sourceRow = Math.floor(row / divisor);
      const sourceColumn = Math.floor(column / divisor);
      const key = `${sourceLevel}/${sourceRow}/${sourceColumn}`;
      let tile = tiles.get(key);
      if (!tile && (!pending || sourceLevel === overviewImageryZoom)) {
        tile = requestTile(sourceLevel, sourceRow, sourceColumn);
      }
      if (!tile) continue;
      tiles.delete(key);
      tiles.set(key, tile);
      used.add(key);
      if (tile.state === 'loaded') return {tile, pending};
      if (tile.state === 'pending') pending = true;
    }
    return {pending};
  }

  function draw() {
    frame = 0;
    if (element.hidden || !center) return;
    const width = element.clientWidth;
    const height = element.clientHeight;
    const worldScale = scale();
    const project = ({x, y}) => ({x: width / 2 + (x - center.x - Math.round(x - center.x)) * worldScale,
      y: height / 2 + (y - center.y) * worldScale});
    const level = Math.min(maximumImageryZoom, Math.floor(zoom));
    const tileScale = 2 ** level;
    const size = worldScale / tileScale;
    const left = center.x * tileScale - width / 2 / size;
    const top = center.y * tileScale - height / 2 / size;
    const used = new Set();
    const visible = new Set();
    let uncovered = 0;
    let pending = false;

    for (let row = Math.max(0, Math.floor(top)); row < Math.min(tileScale, Math.ceil(top + height / size)); row++) {
      for (let column = Math.floor(left); column < Math.ceil(left + width / size); column++) {
        const result = imageryTiles ? findImagery(level, row, column, used) : {};
        if (result.tile) visible.add(result.tile);
        else {
          uncovered++;
          pending ||= result.pending;
        }
      }
    }

    const visibleImages = new Set();
    for (const {image, level: sourceLevel, row, column} of visible) {
      const sourceScale = 2 ** sourceLevel;
      const sourceSize = worldScale / sourceScale;
      const imageLeft = width / 2 + (column - center.x * sourceScale) * sourceSize;
      const imageTop = height / 2 + (row - center.y * sourceScale) * sourceSize;
      const x = Math.round(imageLeft);
      const y = Math.round(imageTop);
      image.style.transform = `translate(${x}px, ${y}px)`;
      image.style.width = Math.round(imageLeft + sourceSize) - x + 'px';
      image.style.height = Math.round(imageTop + sourceSize) - y + 'px';
      image.style.zIndex = sourceLevel;
      visibleImages.add(image);
      if (!image.parentElement) imagery.append(image);
    }
    for (const image of [...imagery.children]) {
      if (!visibleImages.has(image)) image.remove();
    }
    for (const key of tiles.keys()) {
      if (tiles.size <= tileCacheLimit) break;
      if (!used.has(key)) tiles.delete(key);
    }

    for (const {id, outline, ring} of footprints) {
      const active = id === selected;
      outline.classList.toggle('selected', active);
      outline.setAttribute('visibility', active || uncovered ? 'visible' : 'hidden');
      outline.setAttribute('points', ring.map(project).map(({x, y}) => `${x},${y}`).join(' '));
    }
    positionMarkers(markers, (coordinates) => project(mercator(coordinates)), width, height);
    if (!imageryTiles) onStatus('Imagem de satélite indisponível. Os contornos do campus continuam visíveis.');
    else if (!visible.size && pending) onStatus('Carregando imagem de satélite…');
    else if (!pending && uncovered) {
      onStatus('Imagem de satélite indisponível nesta área. Os contornos do campus continuam visíveis.');
    } else onStatus('');
  }

  function fit(bounds, zoomLimit) {
    center = {x: (bounds.left + bounds.right) / 2, y: (bounds.top + bounds.bottom) / 2};
    const availableWidth = Math.max(80, element.clientWidth - 88);
    const availableHeight = Math.max(80, element.clientHeight - 104);
    const fitScale = Math.min(availableWidth / (bounds.right - bounds.left), availableHeight / (bounds.bottom - bounds.top));
    zoom = clamp(Math.log2(fitScale / tileSize), minimumZoom, zoomLimit);
    queueDraw();
  }

  function pan(dx, dy) {
    center.x = clamp(center.x - dx / scale(), panLimits.left, panLimits.right);
    center.y = clamp(center.y - dy / scale(), panLimits.top, panLimits.bottom);
    queueDraw();
  }

  function zoomBy(delta, x = 0, y = 0) {
    const previousScale = scale();
    zoom = clamp(zoom + delta, minimumZoom, maximumZoom);
    const shift = 1 - scale() / previousScale;
    pan(x * shift, y * shift);
  }

  const listeners = new AbortController();
  const {signal} = listeners;
  const pointers = new Map();
  function gesture() {
    const [a, b] = pointers.values();
    if (!b) return a;
    return {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, distance: Math.hypot(a.x - b.x, a.y - b.y)};
  }
  let dragged = false;
  element.addEventListener('pointerdown', (event) => {
    if (event.button !== 0 || pointers.size >= 2) return;
    if (!pointers.size) dragged = false;
    pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    if (pointers.size === 2) dragged = true;
  }, {signal});
  element.addEventListener('pointermove', (event) => {
    if (!pointers.has(event.pointerId)) return;
    const before = gesture();
    pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    const after = gesture();
    if (!dragged && Math.hypot(after.x - before.x, after.y - before.y) < 3) {
      pointers.set(event.pointerId, before);
      return;
    }
    dragged = true;
    element.setPointerCapture(event.pointerId);
    pan(after.x - before.x, after.y - before.y);
    if (before.distance && after.distance) {
      const rect = element.getBoundingClientRect();
      zoomBy(Math.log2(after.distance / before.distance), after.x - rect.left - rect.width / 2,
        after.y - rect.top - rect.height / 2);
    }
  }, {signal});
  for (const event of ['pointerup', 'pointercancel', 'pointerleave', 'lostpointercapture']) {
    element.addEventListener(event, ({pointerId}) => pointers.delete(pointerId), {signal});
  }
  element.addEventListener('click', (event) => { if (dragged) event.stopPropagation(); }, {capture: true, signal});
  element.addEventListener('wheel', (event) => {
    event.preventDefault();
    const rect = element.getBoundingClientRect();
    zoomBy(-Math.sign(event.deltaY) * .28, event.clientX - rect.left - rect.width / 2,
      event.clientY - rect.top - rect.height / 2);
  }, {passive: false, signal});

  function refresh() {
    for (const [key, tile] of tiles) {
      if (tile.state === 'failed') tiles.delete(key);
    }
    queueDraw();
  }
  const observer = new ResizeObserver(queueDraw);
  observer.observe(element);
  window.addEventListener('online', refresh, {signal});

  return {
    refresh,
    destroy() {
      destroyed = true;
      listeners.abort();
      observer.disconnect();
      cancelAnimationFrame(frame);
      tiles.clear();
    },
    select(destination) {
      selected = destination?.id;
      const footprint = footprints.find(({id}) => id === selected);
      const points = footprint?.ring.slice();
      if (destination?.entry.coordinates) points?.push(mercator(destination.entry.coordinates));
      fit(points ? extent(points) : campus, points ? 19.8 : 18.4);
    },
    zoom: zoomBy,
  };
}
