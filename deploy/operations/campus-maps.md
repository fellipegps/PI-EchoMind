# Publicar a maquete de um campus

A equipe EchoMind configura o campus e as geometrias dos blocos. Em **Mapa dos campi**, a instituição pode renomear blocos, gerenciar suas fotos, editar locais internos e cadastrar pontos de referência. As fichas da maquete e da vista de satélite exibem o conteúdo publicado no painel.

## Preparar as geometrias

Inclua estes arquivos em `echomind-front/public/campus-guide/<model_key>/`.

- `buildings.geojson` com os contornos em WGS84. Cada bloco selecionável tem um `Feature.id`, `properties.kind: "destination"`, `properties.heightMeters` e geometria `Polygon`.
- `context.geojson` com as feições do entorno. Use uma `FeatureCollection` vazia se o entorno ainda estiver sendo preparado.
- `destinations.json` com as listas `destinations` e `aboutSources` e o objeto `sources`. Cada destino deve ter o mesmo `id` do contorno, `name`, `shortName`, `kind`, `labelCoordinates` e `entry`. Informe as coordenadas em ordem **longitude, latitude**. Use `entry.coordinates: null` se a entrada não foi identificada.

O acervo de Anápolis fica diretamente em `public/campus-guide/` e usa a chave `anapolis`. Para um campus novo, use os arquivos de Anápolis como referência da estrutura. Confira o enquadramento e as entradas com a instituição e publique o frontend com os arquivos do campus.

## Registrar o campus e os blocos

O portal da instituição precisa existir. Aplique as migrações do banco até `0030` e execute o comando com o ambiente do backend da instituição. O comando usa o slug para isolar o cadastro no portal correto. Execute a partir de `echomind-backend`.

```bash
python -m scripts.configure_campus --slug SLUG_DO_PORTAL --include-model-buildings ../deploy/operations/campus-anapolis.json
```

A opção `--include-model-buildings` cria ou vincula os destinos descritos na maquete. Use `--campus-id` ao atualizar um campus já cadastrado com nome diferente. Para associar blocos com nomes diferentes entre banco e maquete e preservar suas fotos e QR Codes, inclua uma entrada por bloco com o ID de cadastro existente. Para outro campus, use outro manifesto com a chave dos arquivos correspondentes.

Ao abrir o painel de Anápolis pela primeira vez, os blocos existentes são associados às geometrias e os laboratórios do catálogo são incluídos se estiverem ausentes. A preparação é registrada no banco e as edições posteriores ficam disponíveis no painel.

```json
{
  "name": "Campus Anápolis",
  "center_lat": -16.294593,
  "center_lng": -48.944138,
  "zoom": 18,
  "model_key": "anapolis",
  "buildings": [
    {
      "name": "Bloco A",
      "category": "bloco",
      "model_destination_id": "bloco-a",
      "entrance_lat": -16.2945378,
      "entrance_lng": -48.9446974,
      "photos": [
        { "file": "fotos/fachada.jpg", "caption": "Fachada do bloco" }
      ]
    }
  ]
}
```

Inclua o campo `id` no bloco quando precisar apontar para um registro existente específico. O comando reutiliza o vínculo da maquete ou o nome quando o ID não é fornecido. Os caminhos das fotos são relativos ao manifesto. O envio aceita JPEG, PNG e WebP e usa a mesma normalização do painel. Fotos já cadastradas são preservadas por padrão. Use `"replace_photos": true` no bloco para substituí-las pelas fotos listadas no manifesto. Para ocultar um campus ou bloco, passe `"active": false` no registro.

Abra a aba **Locais** do portal e selecione um bloco e um ponto de referência na maquete e no satélite. Confira as fotos, as legendas e os links para as fichas completas. A imagem de satélite depende de `NEXT_PUBLIC_MAP_SATELLITE_TILE_URL` e `NEXT_PUBLIC_MAP_SATELLITE_TILE_ATTRIBUTION` no frontend. Quando o campus ainda não possui maquete, o portal apresenta o mapa geográfico e as fichas dos locais publicados.
