# Mapa e navegação dos campi

O mapa geográfico é configurado separadamente para cada instituição (`tenant_id`). Um administrador pode cadastrar vários campi, entradas de prédios, espaços internos e os caminhos de pedestres. O portal público usa o `public_slug` da instituição e exibe somente dados ativos dela. Os locais do mapa esquemático anterior continuam disponíveis durante a transição.

## Preparação

1. Configure `NEXT_PUBLIC_API_URL` e o acesso administrativo já usados pelo EchoMind.
2. Configure `NEXT_PUBLIC_MAP_TILE_URL` e `NEXT_PUBLIC_MAP_TILE_ATTRIBUTION` conforme o fornecedor de imagens do mapa escolhido. O exemplo em `echomind-front/.env.local.example` usa o servidor público do OpenStreetMap, sujeito à [política de uso](https://operations.osmfoundation.org/policies/tiles/); para implantação institucional, escolha um fornecedor com capacidade e condições adequadas ao tráfego esperado.
   Para cadastrar sobre uma vista aérea, configure também `NEXT_PUBLIC_MAP_SATELLITE_TILE_URL` e `NEXT_PUBLIC_MAP_SATELLITE_TILE_ATTRIBUTION`. Com ambos definidos, o mapa administrativo abre em **Satélite** e permite alternar para **Mapa** sem perder os pontos em edição. Use um serviço que autorize o uso de imagens no aplicativo. O seletor exibe a atribuição textual informada; quando a URL é da [API de imagens aéreas do MapTiler](https://docs.maptiler.com/cloud/api/tiles/), também mostra o [logotipo exigido nas contas gratuitas](https://docs.maptiler.com/guides/map-design/attribution/add-attribution/). Para outros provedores, confira eventuais requisitos adicionais de marca. Sem provedor configurado, o mapa comum continua disponível.
3. Publique o portal em HTTPS. O navegador exige contexto seguro e consentimento do visitante para acompanhar a posição.
4. Aplique as migrations habituais do backend no banco da instituição. Não é necessário PostGIS nem alterar o armazenamento vetorial do RAG.

## Cadastro do campus

1. Acesse `/campi` como administrador e cadastre o nome e o centro do campus.
2. Marque no mapa a **entrada utilizável** de cada prédio. Descreva o prédio e cadastre seus auditórios, laboratórios e demais espaços com o respectivo piso. O ponto da entrada é o destino da navegação externa; o espaço interno aparece como orientação ao chegar.
3. Marque pontos nos cruzamentos e curvas dos caminhos para pedestres e conecte os pontos vizinhos com trechos. Marque trechos que permitem passagem acessível. Caminhos fechados podem ser desativados.
4. Associe cada entrada ao ponto do caminho correspondente, a no máximo 25 m da entrada marcada. Sem esse vínculo, o portal mostra o prédio, mas não calcula uma rota até ele. Confira a rota no portal público antes de divulgar o mapa, inclusive em dispositivo móvel no próprio campus.

Sem uma rede conectada de caminhos, o portal pode exibir o prédio no mapa, mas não deve apresentar uma linha reta como rota caminhável. A qualidade do trajeto depende do levantamento das passagens reais, entradas, barreiras e conexões feito pela instituição.
Imagens aéreas podem estar desatualizadas ou ocultar entradas cobertas; confirme os pontos e os trechos caminháveis no local antes de publicar o mapa.

## Navegação do visitante

O visitante escolhe o campus e o prédio ou espaço de destino. Ao autorizar a localização, o navegador fornece posição e margem de precisão; o trajeto é recalculado sobre os trechos cadastrados conforme a pessoa se move. Também é possível escolher a origem no mapa quando a localização não estiver disponível ou for imprecisa. A posição do visitante é usada no navegador e não precisa ser persistida na API.

O GPS pode perder precisão perto ou dentro de prédios. O recurso orienta até a entrada cadastrada e apresenta as informações do espaço interno; ele não promete identificar automaticamente sala ou andar.

## Isolamento e validação

Todos os cadastros e vínculos de campus, prédio, espaço, ponto e trecho pertencem a um `tenant_id`. A API administrativa valida que IDs relacionados pertencem ao mesmo tenant e campus. A API pública resolve o tenant pelo `public_slug` e não publica itens inativos. Valide também, em campo, os percursos acessíveis, locais sem conexão e comportamento do GPS antes de disponibilizar a navegação aos estudantes.
