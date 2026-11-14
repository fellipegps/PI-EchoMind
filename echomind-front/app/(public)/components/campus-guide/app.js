import {icon} from './icons.js';
import {createSatelliteMap} from './campus-satellite.js';

export function mountCampusGuide(root, {satelliteTiles, placeLinks}) {
  const get = (id) => root.querySelector('#' + id);
  const markersElement = get('markers');
  const about = get('about');
  const mapMessage = get('map-message');
  const mapDetail = get('map-detail');
  const controller = new AbortController();
  const {signal} = controller;
  const aboutButton = get('about-button');
  const credit = get('satellite-attribution');
  const logo = get('satellite-logo');
  const osmCredit = get('osm-credit');
  const usesMapTiler = satelliteTiles?.url.startsWith('https://api.maptiler.com/');
  let destroyScene;
  let destroySatellite;
  if (satelliteTiles) {
    credit.innerHTML = satelliteTiles.attribution;
    if (usesMapTiler) logo.querySelector('img').src = 'https://api.maptiler.com/resources/logo.svg';
  }
  const attributionIncludesOsm = Boolean(credit.querySelector('a[href*="openstreetmap.org/"]'));

  root.querySelectorAll('[data-icon]').forEach((node) => { node.innerHTML = icon(node.dataset.icon); });
  aboutButton.addEventListener('click', () => about.showModal());

  async function readData(file) {
    const response = await fetch('/campus-guide/' + file, {signal});
    if (!response.ok) throw new Error('Falha ao carregar ' + file);
    return response.json();
  }

  function sourceLinks(list, ids, sources) {
    list.replaceChildren(...[...new Set(ids)].map((id) => {
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.textContent = sources[id].label;
      link.href = sources[id].url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      li.append(link);
      return li;
    }));
  }

  async function init() {
    const [{destinations, sources, aboutSources}, buildings, context] = await Promise.all([
      readData('destinations.json'), readData('buildings.geojson'), readData('context.geojson'),
    ]);
    if (signal.aborted) return;
    const buildingById = new Map(buildings.features.map((feature) => [feature.id, feature]));
    const pins = new Map();
    let active, scene;
    let view = '3d';
    let satellite, satelliteSelection, modelSelection;
    const currentScene = () => view === 'satellite' ? satellite : scene;

    function selectInView(destination) {
      currentScene()?.select(destination);
      if (view === 'satellite') satelliteSelection = destination;
      else modelSelection = destination;
    }

    const entryLabel = document.createElement('div');
    entryLabel.className = 'entry-pin';
    entryLabel.hidden = true;
    markersElement.append(entryLabel);
    sourceLinks(get('about-sources'), aboutSources, sources);

    function select(id) {
      const destination = destinations.find((item) => item.id === id);
      if (!destination) return;
      active = destination;
      const confirmed = destination.entry.status === 'confirmed';
      const hasPoint = Boolean(destination.entry.coordinates);
      const laboratories = destination.laboratories ?? [];
      get('map-detail-name').textContent = destination.name;
      get('map-detail-kind').textContent = destination.kind;
      get('map-detail-kind').hidden = laboratories.length > 0;
      get('map-detail-labs').hidden = laboratories.length === 0;
      const labItems = laboratories.map((description) => {
        const item = document.createElement('li');
        item.textContent = description;
        return item;
      });
      get('map-detail-labs').replaceChildren(...labItems);
      mapDetail.hidden = false;
      entryLabel.classList.toggle('confirmed', confirmed);
      entryLabel.innerHTML = icon('door');
      entryLabel.append(confirmed ? 'Entrada' : 'Entrada aproximada');
      entryLabel.hidden = !hasPoint;
      const placeLink = get('public-place-link');
      const href = placeLinks[destination.id];
      placeLink.hidden = !href;
      if (href) placeLink.href = href;
      else placeLink.removeAttribute('href');

      for (const [pinId, pin] of pins) pin.setAttribute('aria-pressed', String(pinId === id));
      selectInView(destination);
    }

    for (const destination of destinations) {
      const pin = document.createElement('button');
      pin.type = 'button';
      pin.className = 'map-pin';
      pin.style.visibility = 'hidden';
      pin.setAttribute('aria-label', destination.name);
      pin.title = destination.name;
      pin.setAttribute('aria-pressed', 'false');
      pin.setAttribute('aria-controls', 'map-detail');
      pin.textContent = destination.shortName;
      pin.addEventListener('click', (event) => {
        select(destination.id);
        if (event.detail === 0) get('public-place-link').focus({preventScroll: true});
      });
      pins.set(destination.id, pin);
      markersElement.append(pin);
    }

    const mapTools = get('map-tools');
    const compass = get('compass');

    function resetSelection(restoreFocus) {
      const previous = active;
      active = undefined;
      mapDetail.hidden = true;
      entryLabel.hidden = true;
      pins.forEach((pin) => pin.setAttribute('aria-pressed', 'false'));
      selectInView(undefined);
      if (restoreFocus && previous) {
        const pin = pins.get(previous.id);
        const focusTarget = pin.style.visibility === 'hidden'
          ? get(view === '3d' ? 'view-3d' : 'view-satellite')
          : pin;
        focusTarget.focus({preventScroll: true});
      }
    }

    get('map-detail-close').addEventListener('click', () => resetSelection(true));
    get('map-stage').addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !mapDetail.hidden) resetSelection(true);
    });
    compass.addEventListener('click', () => scene?.north());
    mapTools.addEventListener('click', (event) => {
      switch (event.target.closest('button')?.dataset.action) {
        case 'zoom-in': currentScene()?.zoom(.55); break;
        case 'zoom-out': currentScene()?.zoom(-.55); break;
        case 'left': scene?.rotate(-30); break;
        case 'right': scene?.rotate(30); break;
        case 'reset': resetSelection(false); break;
      }
    });

    const roofPins = destinations.map((destination) => ({
      id: destination.id, element: pins.get(destination.id), coordinates: destination.labelCoordinates,
      elevation: buildingById.get(destination.id).properties.heightMeters + 3,
    }));

    function visibleMarkers(mode) {
      if (mode !== view) return [];
      const markers = roofPins.map((pin) => pin.id === active?.id
        ? {...pin, priority: 3, popup: mapDetail}
        : {...pin, priority: pin.id === 'ginasio' ? 1 : 0});
      if (active?.entry.coordinates) markers.push({element: entryLabel, coordinates: active.entry.coordinates, elevation: 0, priority: 2});
      return markers;
    }

    function showMapMessage(message) {
      if (mapMessage.textContent !== message) mapMessage.textContent = message;
      mapMessage.hidden = !message;
    }

    const modelButton = get('view-3d');
    const satelliteButton = get('view-satellite');
    const satelliteElement = get('satellite-map');
    function switchView(mode) {
      if (view === mode) return;
      view = mode;
      const showingSatellite = mode === 'satellite';
      pins.forEach((pin) => { pin.style.visibility = 'hidden'; });
      entryLabel.style.visibility = 'hidden';
      showMapMessage('');
      modelButton.setAttribute('aria-pressed', String(!showingSatellite));
      satelliteButton.setAttribute('aria-pressed', String(showingSatellite));
      get('map').hidden = showingSatellite;
      satelliteElement.hidden = !showingSatellite;
      get('rotate-control').hidden = showingSatellite;
      compass.disabled = !scene;
      compass.hidden = showingSatellite;
      credit.hidden = !showingSatellite || !satelliteTiles;
      logo.hidden = !showingSatellite || !usesMapTiler;
      osmCredit.hidden = showingSatellite && attributionIncludesOsm;

      if (showingSatellite && !satellite) {
        satellite = createSatelliteMap({element: satelliteElement, buildings, onSelect: select, onStatus: showMapMessage,
          markers: () => visibleMarkers('satellite'), tiles: satelliteTiles});
        destroySatellite = satellite.destroy;
        selectInView(active);
      } else if (active !== (showingSatellite ? satelliteSelection : modelSelection)) {
        selectInView(active);
      }
      currentScene()?.refresh();
      mapTools.querySelectorAll('button').forEach((button) => { button.disabled = !currentScene(); });
    }

    modelButton.addEventListener('click', () => switchView('3d'));
    satelliteButton.addEventListener('click', () => switchView('satellite'));

    let sceneFailed = false;
    try {
      const {createDetailedCampus} = await import('./campus-scene.js');
      if (signal.aborted) return;
      scene = createDetailedCampus({
        element: get('map'), buildings, context, destinations,
        onSelect: select,
        onBearing: (bearing) => { get('north-arrow').style.rotate = -bearing + 'deg'; },
        markers: () => visibleMarkers('3d'),
      });
      destroyScene = scene.destroy;
      compass.disabled = false;
      if (view === '3d' && active) selectInView(active);
      scene.refresh();
    } catch (error) {
      if (signal.aborted) return;
      console.error(error);
      sceneFailed = true;
      if (view === '3d') switchView('satellite');
      showMapMessage('A maquete 3D não pôde ser carregada. Você pode usar a visão de satélite.');
    }
    modelButton.disabled = sceneFailed;
    satelliteButton.disabled = false;
    mapTools.querySelectorAll('button').forEach((button) => { button.disabled = false; });
  }

  init().catch((error) => {
    if (signal.aborted) return;
    console.error(error);
    mapMessage.textContent = 'Não foi possível carregar os dados do campus.';
    mapMessage.hidden = false;
  });

  return () => {
    controller.abort();
    destroyScene?.();
    destroySatellite?.();
    if (about.open) about.close();
  };
}
