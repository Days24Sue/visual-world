# Visual World · Data Sources V0.2

## 已实现作品源

| ID | Source | Mode | Image strategy | Notes |
|---|---|---|---|---|
| met | The Met | bulk CSV | metadata first; image rights per object | Large CC0 metadata dataset |
| moma | MoMA | bulk CSV | metadata only | Dataset images excluded |
| nga | National Gallery of Art | CSV join + IIIF | only `published_images.openaccess=1` | Daily/frequent open-data updates |
| artic | Art Institute of Chicago | REST + IIIF | IIIF from `image_id` | Full API pagination |
| cleveland | Cleveland Museum of Art | REST | Open Access URLs where provided | CC0 qualifying assets |
| rijks | Rijksmuseum | OAI-PMH | EDM/IIIF URLs + record rights | resumptionToken full harvest |
| tate | Tate | bulk CSV snapshot | thumbnail link only | Snapshot last updated Oct 2014 |
| whitney | Whitney Museum | bulk CSV | metadata only | Current CC0 open-access dataset |
| mplus | M+ Museum | two bulk CSVs | metadata only | Modern/contemporary Asian visual culture |
| walters | Walters Art Museum | static CSVs | joins media where fields resolve | Static replacement after API v1 closure |
| smithsonian | Smithsonian Open Access | public S3 NDJSON | CC0 media only | Art/design units by default; all units optional |

## 已实现资源索引

| ID | Source | Mode | Purpose |
|---|---|---|---|
| awesome_illustrations | Awesome Illustrations | Markdown link harvest | Modern illustration libraries/resources |
| design_resources | Design Resources | Markdown link harvest | Illustration + graphic/design resource discovery |
| art_datasets | Art Datasets | Markdown link harvest | More museum/dataset leads for future connectors |

## 下一批建议接入

Wellcome Collection (daily snapshot + IIIF), Minneapolis Institute of Art, Getty Museum, SMK Denmark, Wikimedia Commons/Wikidata, Europeana, Paris Musées, 3x3 Illustration, Inspiration Grid.

其中 3x3 / Inspiration Grid 应以索引、作者、项目页和允许展示的缩略图为主，不应把受版权保护的现代插画原图全量复制到本地。
