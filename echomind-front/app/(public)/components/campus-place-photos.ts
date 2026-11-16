import { campusPhotoUrl, type PlacePhoto } from "@/lib/geocampus-api";
import styles from "./campus-place-photos.module.css";

export function campusPlacePhotos(photos: PlacePhoto[], name: string) {
  const gallery = document.createElement("div");
  gallery.className = styles.gallery;
  gallery.setAttribute("aria-label", "Fotos de " + name);
  gallery.setAttribute("role", "group");
  if (photos.length > 1) gallery.tabIndex = 0;

  for (const photo of photos) {
    const url = campusPhotoUrl(photo.url);
    if (!url) continue;
    const figure = document.createElement("figure");
    const image = document.createElement("img");
    image.src = url;
    image.alt = photo.caption || "Foto de " + name;
    image.loading = "lazy";
    image.decoding = "async";
    figure.append(image);
    image.addEventListener("error", () => {
      figure.remove();
      if (!gallery.childElementCount) gallery.remove();
    }, { once: true });
    if (photo.caption) {
      const caption = document.createElement("figcaption");
      caption.textContent = photo.caption;
      figure.append(caption);
    }
    gallery.append(figure);
  }

  return gallery;
}
