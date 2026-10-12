# Maquette expo garage PAGAL Collection / Atelier – kit Bambu P1S

Façade **750 mm** (échelle ≈ 1:26,7) · 750 × 675 × 300 mm assemblée · modèle **creux** (murs 2,4 mm) · **toutes les fenêtres et portes ajourées** (bandeau vitré de l'étage avec ses montants) · cotes estimées d'après photos.

## Pièces (`pieces/`) – toutes ≤ 250 × 236 × 188 mm, sans support
Nom = **rangée** (A avant orange, B milieu, C arrière) + **colonne** (1 gauche → 3 côté arrondi) + **niveau** :
- `B` murs du bas (0 → 3 m) · `H` murs du haut (posés sur le plafond du portique) · `T` toits (couvercles) · `P` terrasse + pergola
- Numéro gravé sous la pièce quand la place le permet ; sinon marquer au feutre à la sortie du plateau.
- Orientation : telles qu'exportées (déjà à plat). `assemblage.json` = position de chaque pièce dans la maquette.

## Accessoires (`accessoires/`)
Enseignes PAGAL / ATELIER : charger `_panneau` + `_lettrage` ensemble (« un objet, plusieurs pièces ») pour le multicolore AMS. Enseignes latérales vierges (coller un sticker du logo). Auvent de porte. Éclisses à coller à l'intérieur sur les joints.

## Réglages conseillés (Bambu Studio)
0,2 mm · 2 parois · 4 couches dessus / 3 dessous · remplissage **Éclair (lightning) 10 %** · pas de support.
Estimation (PrusaSlicer, mêmes réglages) : **≈ 3,4 kg PLA, ≈ 120 h** (≈ 4 bobines).

## Vitrages (optionnel)
Coller à l'intérieur une feuille transparente ou fumée (rhodoid / PETG 0,5 mm) derrière les ouvertures. Une bande LED à l'intérieur fait bel effet en expo.

## Assemblage
Poser sur un plateau rigide (MDF/Forex 80 × 70 cm). Coller rangée par rangée : B, puis H (leur rebord inférieur repose sur le haut des murs B), puis T et P. Colle CA + éclisses aux joints verticaux.

## Regénérer
`pip install trimesh manifold3d shapely matplotlib` puis `python3 garage_pagal.py [largeur_mm]`.
