# Maquette garage PAGAL Collection / Atelier

Modèle reconstruit à partir de 6 photos (pas de photogrammétrie : modélisation paramétrique, cotes estimées).

| Fichier | Contenu |
|---|---|
| `garage_pagal_1-150.stl` | Maquette complète, une seule pièce (149 × 131 × 55 mm) |
| `garage_pagal_1-150_orange.stl` / `_gris.stl` / `_details_noirs.stl` / `_socle.stl` | Mêmes volumes séparés pour impression multicolore (AMS / MMU) – à charger ensemble, ils sont déjà positionnés |
| `garage_pagal.py` | Script source : toutes les cotes (en mètres) en tête de fichier |

Regénérer à une autre échelle : `pip install trimesh manifold3d shapely matplotlib` puis `python3 garage_pagal.py 100` (→ 1:100).

Impression : supports nécessaires sous le portique (avancée de 3 m) et sous la pergola, ou imprimer en résine.
