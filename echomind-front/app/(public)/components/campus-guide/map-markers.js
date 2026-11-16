function positionPopup(popup, point, width, height, half) {
  const padding = 12;
  const toolbarWidth = 72;
  const minimumTop = Math.min(60, height / 4);
  const maximumTop = Math.max(minimumTop, height - popup.offsetHeight - 52);
  const maximumLeft = Math.max(padding, width - toolbarWidth - popup.offsetWidth);
  let left = padding;
  if (point) {
    const right = point.x + half + padding;
    left = right <= maximumLeft ? right : point.x - half - padding - popup.offsetWidth;
  }
  const top = point ? point.y - popup.offsetHeight / 2 : maximumTop;
  popup.style.setProperty('--map-detail-left', Math.max(padding, Math.min(left, maximumLeft)) + 'px');
  popup.style.setProperty('--map-detail-top', Math.max(minimumTop, Math.min(top, maximumTop)) + 'px');
}

export function positionMarkers(markers, project, width, height) {
  const occupied = [];
  const ordered = markers().slice().sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
  for (const marker of ordered) {
    const pin = marker.element;
    if (pin.hidden) continue;
    const point = project(marker.coordinates, marker.elevation);
    const half = (pin.offsetWidth || 34) / 2 + 2;
    const pinHeight = (pin.offsetHeight || 31) + 3;
    const bounds = point && {left: point.x - half, right: point.x + half, top: point.y - pinHeight, bottom: point.y + 3};
    const outside = !bounds || bounds.left < 0 || bounds.right > width || bounds.top < 0 || bounds.bottom > height;
    if (marker.popup && width > 0 && height > 0) positionPopup(marker.popup, outside ? null : point, width, height, half);
    const collides = bounds && occupied.some((other) => bounds.left < other.right && bounds.right > other.left
      && bounds.top < other.bottom && bounds.bottom > other.top);
    if (outside || (collides && (marker.priority ?? 0) < 2)) {
      pin.style.visibility = 'hidden';
      continue;
    }
    pin.style.visibility = '';
    pin.style.transform = 'translate(' + point.x + 'px, ' + point.y + 'px)';
    occupied.push(bounds);
  }
}
