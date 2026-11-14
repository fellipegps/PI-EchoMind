export const campusGuideMarkup = `
  <section class="map-stage" id="map-stage" aria-label="Mapa interativo do campus">
    <div class="map" id="map"></div>
    <div class="map satellite-map" id="satellite-map" hidden></div>
    <div class="markers" id="markers">
    </div>
    <section class="map-detail" id="map-detail" aria-labelledby="map-detail-name" hidden>
      <div class="map-detail-header">
        <h2 id="map-detail-name"></h2>
        <button id="map-detail-close" type="button" aria-label="Fechar ficha"><span data-icon="close" aria-hidden="true"></span></button>
      </div>
      <p id="map-detail-kind" hidden></p>
      <ul id="map-detail-labs" aria-label="Laboratórios" hidden></ul>
      <a id="public-place-link" class="public-place-link">Abrir ficha completa</a>
    </section>
    <div class="map-top">
      <div class="view-switch" role="group" aria-label="Vista do mapa">
        <button type="button" id="view-3d" aria-pressed="true" aria-controls="map" disabled><span data-icon="layers" aria-hidden="true"></span>Maquete 3D</button>
        <button type="button" id="view-satellite" aria-pressed="false" aria-controls="satellite-map" disabled><span data-icon="satellite" aria-hidden="true"></span>Satélite</button>
      </div>
      <div class="map-orientation">
        <button class="about-button" id="about-button" type="button" aria-label="Sobre o mapa" title="Sobre o mapa"><span data-icon="info" aria-hidden="true"></span></button>
        <button class="compass" id="compass" type="button" disabled aria-label="Orientar para o norte" title="Orientar para o norte"><span>N</span><span data-icon="north" id="north-arrow" aria-hidden="true"></span></button>
      </div>
    </div>
    <div class="map-dock">
      <div class="map-tools" id="map-tools" role="group" aria-label="Controles do mapa">
        <div class="tool-group">
          <button type="button" disabled data-action="zoom-in" aria-label="Aproximar" title="Aproximar"><span data-icon="plus" aria-hidden="true"></span></button>
          <button type="button" disabled data-action="zoom-out" aria-label="Afastar" title="Afastar"><span data-icon="minus" aria-hidden="true"></span></button>
        </div>
        <div class="tool-group" id="rotate-control">
          <button type="button" disabled data-action="left" aria-label="Girar à esquerda" title="Girar à esquerda"><span data-icon="rotate-left" aria-hidden="true"></span></button>
          <button type="button" disabled data-action="right" aria-label="Girar à direita" title="Girar à direita"><span data-icon="rotate-right" aria-hidden="true"></span></button>
        </div>
        <div class="tool-group"><button type="button" disabled data-action="reset" aria-label="Restaurar vista geral" title="Restaurar vista geral"><span data-icon="locate" aria-hidden="true"></span></button></div>
      </div>
      <div class="map-bottom">
        <a id="satellite-logo" href="https://www.maptiler.com/" target="_blank" rel="noopener noreferrer" hidden><img width="90" height="22" alt="MapTiler"></a>
        <div class="map-credit">
          <span id="satellite-attribution" hidden></span>
          <a id="osm-credit" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer" title="© Contribuidores do OpenStreetMap · ODbL">© OpenStreetMap</a>
        </div>
      </div>
    </div>
    <div class="map-status-stack">
      <p class="map-message" id="map-message" role="status" hidden></p>
    </div>
  </section>
<dialog id="about" aria-labelledby="about-title">
  <div class="dialog-heading"><h2 id="about-title">Sobre o mapa</h2><form method="dialog"><button type="submit" aria-label="Fechar"><span data-icon="close" aria-hidden="true"></span></button></form></div>
  <p>Arraste para girar. Use a roda do mouse ou o gesto de pinça para aproximar. Arraste com o botão direito ou com dois dedos para se deslocar. Selecione um prédio para ver sua fachada de perto.</p>
  <p>Em Satélite, arraste para mover o mapa e selecione os mesmos balões. A imagem aérea precisa de conexão com a internet.</p>
  <p>A base cartográfica é do OpenStreetMap. As fachadas e alturas são ilustrativas. Algumas divisões entre blocos e posições são aproximadas e os acessos marcados precisam de conferência.</p>
  <ul id="about-sources"></ul>
</dialog>
`;
