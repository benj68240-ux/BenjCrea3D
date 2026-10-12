"""
Maquette du garage PAGAL Collection / Atelier, reconstruite a partir des photos.

Modele parametrique (CSG) : toutes les cotes sont en METRES (estimees a partir
des photos, a ajuster si tu as les vraies cotes), puis mises a l'echelle SCALE
a l'export. Repere :
  x : le long de la facade principale, 0 = angle droit (cote portique),
      LONG = angle arrondi (cote entree PAGAL)
  y : 0 = facade principale (orange), DEPTH = facade arriere (portes sectionnelles)
  z : hauteur

Usage : python3 garage_pagal.py [echelle]   (defaut 150 -> maquette 1:150)
Sorties (en mm) : garage_pagal_1-<echelle>.stl  + pieces separees pour multicolore.
"""
import sys
import numpy as np
import trimesh
import shapely.geometry as sg
from shapely.geometry.polygon import orient
from manifold3d import Manifold, CrossSection, FillRule, OpType, set_circular_segments
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties

set_circular_segments(48)

SCALE = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0
TEXT = True            # lettrage en relief PAGAL / ATELIER
GROOVES = True         # rainures du bardage gris

# ---------------- cotes principales (m) ----------------
LONG = 20.0            # longueur facade
DEPTH = 17.0           # profondeur totale
ORANGE_D = 4.6         # profondeur du bloc orange (etage vitre)
ORANGE_H = 8.0
CURVE_R = 2.5          # rayon de l'angle arrondi
TALL_Y1 = 13.9         # fin du volume gris haut / debut terrasse
TALL_H = 7.8
LOW_H = 4.9            # volume gris arriere (sous la terrasse)
PORTICO_D = 3.0        # profondeur du portique a colonnes
PORTICO_X1 = 8.2       # fin du portique
PASSAGE_X1 = 10.7      # passage "ATELIER"
CEIL_H = 3.0           # sous-face de l'etage
RIBBON_Z = (4.0, 6.0)  # bandeau vitre de l'etage
DOOR_H, SECT_H = 2.15, 2.4
REC = 0.25             # profondeur des vitrages en retrait (1,7 mm au 1:150)


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def union(parts):
    return Manifold.batch_boolean(parts, OpType.Add)


def poly_to_cs(poly):
    polys = poly.geoms if hasattr(poly, "geoms") else [poly]
    rings = []
    for p in polys:
        p = orient(p, 1.0)
        rings.append(np.array(p.exterior.coords[:-1]))
        rings += [np.array(i.coords[:-1]) for i in p.interiors]
    return CrossSection(rings, FillRule.EvenOdd)


def extrude(poly, z0, z1):
    return poly_to_cs(poly).extrude(z1 - z0).translate((0, 0, z0))


# Ouvertures : face = 'front' (y=0), 'rear' (y=DEPTH), 'left' (x=0), 'right' (x=LONG)
def opening(face, a0, a1, z0, z1, depth=REC, panes=1, mull=0.12):
    w = (a1 - a0 - mull * (panes - 1)) / panes
    out = []
    for i in range(panes):
        s0 = a0 + i * (w + mull)
        s1 = s0 + w
        if face == "front":
            out.append(box(s0, s1, -1, depth, z0, z1))
        elif face == "rear":
            out.append(box(s0, s1, DEPTH - depth, DEPTH + 1, z0, z1))
        elif face == "left":
            out.append(box(-1, depth, s0, s1, z0, z1))
        elif face == "right":
            out.append(box(LONG - depth, LONG + 1, s0, s1, z0, z1))
    return out


def text_plate(txt, cx, cz, height, face_y, thick):
    """Lettrage en relief sur un plan vertical y=face_y, sortant vers -y."""
    tp = TextPath((0, 0), txt, size=1.0, prop=FontProperties(family="DejaVu Sans", weight="bold"))
    rings = [p for p in tp.to_polygons() if len(p) > 2]
    allp = np.vstack(rings)
    (xmin, ymin), (xmax, ymax) = allp.min(0), allp.max(0)
    k = height / (ymax - ymin)
    rings = [((r - [(xmin + xmax) / 2, (ymin + ymax) / 2]) * k) for r in rings]
    cs = CrossSection(rings, FillRule.EvenOdd)
    # extrusion le long de z puis rotation : (u,v,w) -> (x, -w, v)
    return cs.extrude(thick).rotate((90, 0, 0)).translate((cx, face_y, cz))


# ======================= BLOC ORANGE =======================
corner = sg.box(LONG - CURVE_R, -1, LONG + 1, CURVE_R).difference(
    sg.Point(LONG - CURVE_R, CURVE_R).buffer(CURVE_R, 64))
orange_plan = sg.box(0, 0, LONG, ORANGE_D).difference(corner)

orange = extrude(orange_plan, 0, ORANGE_H)
cuts = [
    extrude(orange_plan.buffer(-0.25), ORANGE_H - 0.3, ORANGE_H + 1),       # toit / acrotere
    box(-1, PORTICO_X1, -1, PORTICO_D, -1, CEIL_H),                          # portique
    box(PORTICO_X1, PASSAGE_X1, -1, ORANGE_D - 0.3, -1, CEIL_H),             # passage atelier
]
# bandeau vitre qui suit l'arrondi, avec meneaux
ring = orange_plan.difference(orange_plan.buffer(-REC))
ring = ring.intersection(sg.box(0.5, -1, LONG + 1, 1.8))
c = np.array([LONG - CURVE_R, CURVE_R])
mullions = [sg.box(x - 0.06, -1, x + 0.06, 1) for x in np.arange(0.5, LONG - CURVE_R, 1.25)[1:]]
for ang in np.radians([-75, -55, -35]):
    d = np.array([np.cos(ang), np.sin(ang)])
    n = np.array([-d[1], d[0]]) * 0.06
    p0, p1 = c + d * (CURVE_R - 1), c + d * (CURVE_R + 1)
    mullions.append(sg.Polygon([p0 - n, p1 - n, p1 + n, p0 + n]))
ring = ring.difference(sg.MultiPolygon(mullions).buffer(0))
cuts.append(extrude(ring, *RIBBON_Z))
# facade avant : fente vitree, entree vitree (sous l'auvent), porte fond du passage
cuts += opening("front", 11.3, 13.2, 1.0, 1.5)
cuts += opening("front", 14.65, 16.95, 0, 2.7, depth=0.45, panes=3, mull=0.1)
cuts.append(box(PORTICO_X1 + 0.4, PASSAGE_X1 - 0.4, 0, ORANGE_D - 0.15, 0, 2.6))
# pignon gauche : grande baie 4 vantaux a l'etage, porte de service
cuts += opening("left", 0.8, 4.0, 4.0, 6.2, panes=4)
cuts += opening("left", 3.4, 4.2, 0, DOOR_H)
orange = orange - union(cuts)

# ======================= VOLUMES GRIS (bardage) =======================
tall = box(0, LONG, ORANGE_D - 0.1, TALL_Y1, 0, TALL_H)   # recouvre le bloc orange (soudure)
tall = tall - box(0.2, LONG - 0.2, ORANGE_D + 0.2, TALL_Y1 - 0.2, TALL_H - 0.25, TALL_H + 1)
low = box(0, LONG, TALL_Y1, DEPTH, 0, LOW_H)
low = low - box(0.2, LONG - 0.2, TALL_Y1, DEPTH - 0.2, LOW_H - 0.3, LOW_H + 1)   # terrasse
grey = tall + low

gcuts = []
if GROOVES:
    pitch, gh, gd = 0.4, 0.12, 0.06
    for z in np.arange(0.5, TALL_H - 0.3, pitch):
        gcuts.append(box(-1, gd, ORANGE_D + 0.05, DEPTH + 1, z, z + gh))        # pignon gauche
        gcuts.append(box(LONG - gd, LONG + 1, ORANGE_D + 0.05, DEPTH + 1, z, z + gh))  # droit
        if z < LOW_H - 0.2:
            gcuts.append(box(-1, LONG + 1, DEPTH - gd, DEPTH + 1, z, z + gh))  # facade arriere
        elif z > LOW_H - 0.25:
            gcuts.append(box(0.2, LONG - 0.2, TALL_Y1 - 0.2, TALL_Y1 + gd, z, z + gh))  # mur terrasse
# facade arriere (de droite a gauche sur la photo 3)
gcuts += opening("rear", 17.4, 19.6, 0, SECT_H, depth=0.12, panes=1)             # porte sectionnelle
gcuts += opening("rear", 14.8, 16.7, 0, SECT_H, depth=0.6)                        # porte ouverte
gcuts += opening("rear", 12.5, 14.4, 0, SECT_H, depth=0.12)                       # porte sectionnelle
gcuts += opening("rear", 9.8, 11.8, 1.4, 2.1, panes=2)
gcuts += opening("rear", 7.5, 9.4, 1.4, 2.1, panes=2)
gcuts += opening("rear", 6.6, 7.4, 0, DOOR_H)
gcuts += opening("rear", 5.6, 6.5, 0, DOOR_H)
gcuts += opening("rear", 3.9, 4.8, 1.4, 2.1)
gcuts += opening("rear", 2.1, 3.0, 1.4, 2.1)
gcuts += opening("rear", 0.6, 1.6, 0, DOOR_H)
# pignon droit (photo 4)
gcuts += opening("right", 5.0, 5.9, 0, DOOR_H)
gcuts += opening("right", 9.6, 11.5, 0, SECT_H, depth=0.6)                       # porte ouverte
gcuts += opening("right", 14.2, 16.1, 1.4, 2.2, panes=2)
# pignon gauche (photos 2 et 6)
gcuts += opening("left", 5.0, 5.9, 0, DOOR_H)
gcuts += opening("left", 9.7, 11.6, 0, SECT_H, depth=0.12)
gcuts += opening("left", 11.75, 12.55, 0, DOOR_H)
gcuts += opening("left", 6.8, 7.3, 5.2, 6.0)
grey = grey - union(gcuts)

# ======================= DETAILS =======================
details = []
# colonnes du portique
for x in [0.25, 2.1, 4.0, 6.1, 8.0]:
    details.append(Manifold.cylinder(CEIL_H + 0.05, 0.18).translate((x, 0.25, 0)))
# auvent / encadrement de l'entree
details.append(box(14.3, 17.3, -0.6, 0.0, 0, 3.0) - box(14.65, 16.95, -1, 0.1, -0.1, 2.7))
# petit auvent porte pignon gauche
details.append(box(-0.6, 0.02, 3.3, 4.3, 2.3, 2.4))
# enseignes (panneaux)
signs = [
    box(13.2, 17.1, -0.08, 0.02, 6.3, 7.3),          # PAGAL collection
    box(PORTICO_X1, PASSAGE_X1, -0.1, 0.02, 3.0, 3.6),  # ATELIER
    box(LONG - 0.02, LONG + 0.08, 10.2, 13.0, 5.0, 6.7),  # enseigne pignon droit
    box(-0.08, 0.02, 10.2, 12.9, 5.0, 6.7),          # enseigne pignon gauche
]
if TEXT:
    signs.append(text_plate("PAGAL", 15.4, 6.85, 0.45, -0.07, 0.06))
    signs.append(text_plate("ATELIER", (PORTICO_X1 + PASSAGE_X1) / 2, 3.3, 0.3, -0.09, 0.06))
# pergola de la terrasse
pz0, pz1 = LOW_H - 0.3, 6.7
posts = np.linspace(0.2, LONG - 0.2, 11)
for x in posts:
    details.append(box(x - 0.1, x + 0.1, DEPTH - 0.3, DEPTH - 0.1, pz0, pz1))
    details.append(box(x - 0.1, x + 0.1, TALL_Y1 - 0.05, DEPTH - 0.1, pz1 - 0.2, pz1))
details.append(box(0.1, LONG - 0.1, DEPTH - 0.3, DEPTH - 0.1, pz1 - 0.2, pz1))
details.append(box(0.1, LONG - 0.1, TALL_Y1 - 0.05, TALL_Y1 + 0.15, pz1 - 0.2, pz1))

# socle / trottoir
base = box(-1.2, LONG + 1.2, -1.6, DEPTH + 1.0, -0.3, 0.0)

parts = {
    "orange": orange,
    "gris": grey,
    "details_noirs": union(details + signs),
    "socle": base,
}
full = union(list(parts.values()))

k = 1000.0 / SCALE   # m -> mm a l'echelle
tag = f"1-{int(SCALE)}"


def save(man, name):
    mesh = man.to_mesh()
    tm = trimesh.Trimesh(mesh.vert_properties[:, :3] * k, mesh.tri_verts, process=True)
    tm.export(name)
    return tm


tm = save(full, f"garage_pagal_{tag}.stl")
for n, p in parts.items():
    save(p, f"garage_pagal_{tag}_{n}.stl")
print("watertight:", tm.is_watertight, "| triangles:", len(tm.faces))
print("dimensions (mm):", np.round(tm.extents, 1))
