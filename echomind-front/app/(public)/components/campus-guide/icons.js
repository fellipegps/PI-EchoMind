const paths = {
  sport: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3v18m-6-16c4 4 4 10 0 14M18 5c-4 4-4 10 0 14"/>',
  map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15m6-12v15"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/>',
  book: '<path d="M12 6c-2-2-6-2-9-1v13c3-1 7-1 9 1 2-2 6-2 9-1V5c-3-1-7-1-9 1v13"/>',
  building: '<path d="M4 21h16M6 21V4h12v17M9 8h.01M15 8h.01M9 12h.01m6 0h.01M10 21v-5h4v5"/>',
  door: '<path d="M3 21h18M6 21V4h12v17M14 12h.01"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  satellite: '<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4a12 12 0 0 1 0 16 12 12 0 0 1 0-16Z"/>',
  north: '<path fill="currentColor" stroke="none" d="M12 2 6 18l6-4 6 4z"/>',
  'arrow-left': '<path d="m11 6-6 6 6 6M5 12h14"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  'rotate-left': '<path d="M3 4v6h6M3.6 10A8 8 0 1 1 5 17"/>',
  'rotate-right': '<path d="M21 4v6h-6m5.4 0A8 8 0 1 0 19 17"/>',
  locate: '<circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4"/>',
  position: '<path d="m21 3-6 18-4-8-8-4 18-6z"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
};

export function icon(name) {
  return `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
}
