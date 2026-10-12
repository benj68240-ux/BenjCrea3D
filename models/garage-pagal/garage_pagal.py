"""
Maquette d'exposition du garage PAGAL Collection / Atelier (photos -> CSG).

Toutes les cotes du batiment sont en METRES (estimees a partir des photos, a
ajuster avec les vraies cotes), puis mises a l'echelle pour que la facade fasse
WIDTH_MM. Le modele est CREUX (murs d'environ 2,5 mm, toits = couvercles
imprimes a part) puis decoupe en pieces qui tiennent sur le plateau d'une
Bambu Lab P1S (256 x 256 x 256 mm), sans support.

Repere :  x = facade principale (0 = angle droit cote portique)
          y = profondeur (0 = facade orange, DEPTH = facade arriere)
          z = hauteur

Usage : python3 garage_pagal.py [largeur_mm]     (defaut 750)
Sorties : pieces/<ID>.stl, accessoires/*.stl
"""
import json
import os
import sys
import numpy as np
import trimesh
import shapely.geometry as sg
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from manifold3d import Manifold, CrossSection, FillRule, OpType, set_circular_segments
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties

set_circular_segments(64)

WIDTH_MM = float(sys.argv[1]) if len(sys.argv) > 1 else 750.0

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
REC = 0.15             # epaisseur du bandeau vitre (> mur : ajoure)
THRU = 0.3             # profondeur de coupe des ouvertures : traverse le mur (ouvrants ajoures)
SLAB_Y0, SLAB_T = -1.0, 0.05  # trottoir devant + sol du portique

K = WIDTH_MM / LONG    # mm par metre (750 mm -> echelle 1:26,7)

# ---------------- coque / decoupe ----------------
T = 2.4 / K            # epaisseur des murs
GD = 1.1 / K           # profondeur des rainures du bardage
FLANGE = 15.0 / K      # rebord de collage sous les pieces du haut
STEP = 6.0 / K         # rebord de collage a 45 deg en haut des murs (sans support)
PLATE = 1.6 / K        # plafond du portique / rebords
X_CUTS = [LONG / 3, 2 * LONG / 3]
Y_CUTS = [ORANGE_D, 10.9]          # separe aussi l'orange du gris (une couleur par piece)
Z_CUT = CEIL_H                     # la sous-face du portique est posee sur le plateau
Z_LID_HIGH = 7.45                  # couvercles : toit orange + toit gris haut (plaque ~4 mm sous le toit gris)
Z_LID_LOW = 4.5                    # couvercle : terrasse + pergola
ROWS = "ABC"                       # A = avant (orange), C = arriere

OPENINGS = []          # volumes exterieurs en creux (portique, passage) : mur garde autour dans la coque


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def cutbox(x0, x1, y0, y1, z0, z1):
    OPENINGS.append((x0, x1, y0, y1, z0, z1))
    return box(x0, x1, y0, y1, z0, z1)


def union(parts):
    return Manifold.batch_boolean(parts, OpType.Add)


def poly_to_cs(poly):
    polys = poly.geoms if hasattr(poly, "geoms") else [poly]
    rings = []
    for p in polys:
        if p.is_empty:
            continue
        p = orient(p, 1.0)
        rings.append(np.array(p.exterior.coords[:-1]))
        rings += [np.array(i.coords[:-1]) for i in p.interiors]
    return CrossSection(rings, FillRule.EvenOdd)


def cs_to_shapely(cs):
    geom = sg.GeometryCollection()
    for r in cs.to_polygons():
        if len(r) > 2:
            geom = geom.symmetric_difference(sg.Polygon(r).buffer(0))
    return geom


def extrude(poly, z0, z1):
    return poly_to_cs(poly).extrude(z1 - z0).translate((0, 0, z0))


def text_cs(txt, height, bold=True):
    """Texte centre sur (0,0), hauteur 'height' (unites du modele)."""
    tp = TextPath((0, 0), txt, size=1.0,
                  prop=FontProperties(family="DejaVu Sans", weight="bold" if bold else "normal"))
    rings = [p for p in tp.to_polygons() if len(p) > 2]
    allp = np.vstack(rings)
    (xmin, ymin), (xmax, ymax) = allp.min(0), allp.max(0)
    k = height / (ymax - ymin)
    rings = [(r - [(xmin + xmax) / 2, (ymin + ymax) / 2]) * k for r in rings]
    return CrossSection(rings, FillRule.EvenOdd), (xmax - xmin) * k


def opening(face, a0, a1, z0, z1, panes=1, mull=0.1):
    """Ouverture ajouree (traverse le mur). face = front (y=0), rear (y=DEPTH), left (x=0), right (x=LONG)."""
    depth = THRU
    w = (a1 - a0 - mull * (panes - 1)) / panes
    out = []
    for i in range(panes):
        s0 = a0 + i * (w + mull)
        s1 = s0 + w
        out.append({
            "front": lambda: box(s0, s1, -1, depth, z0, z1),
            "rear": lambda: box(s0, s1, DEPTH - depth, DEPTH + 1, z0, z1),
            "left": lambda: box(-1, depth, s0, s1, z0, z1),
            "right": lambda: box(LONG - depth, LONG + 1, s0, s1, z0, z1),
        }[face]())
    return out


# ======================= BLOC ORANGE =======================
corner = sg.box(LONG - CURVE_R, -1, LONG + 1, CURVE_R).difference(
    sg.Point(LONG - CURVE_R, CURVE_R).buffer(CURVE_R, 64))
orange_plan = sg.box(0, 0, LONG, ORANGE_D).difference(corner)

orange = extrude(orange_plan, 0, ORANGE_H)
cuts = [
    extrude(orange_plan.buffer(-0.25), ORANGE_H - 0.3, ORANGE_H + 1),       # toit / acrotere
    cutbox(-1, PORTICO_X1, -1, PORTICO_D, -1, CEIL_H),                       # portique
    cutbox(PORTICO_X1, PASSAGE_X1, -1, ORANGE_D - 0.3, -1, CEIL_H),          # passage atelier
]
# bandeau vitre qui suit l'arrondi, avec meneaux
ring = orange_plan.difference(orange_plan.buffer(-REC))
ring = ring.intersection(sg.box(0.5, -1, LONG + 1, 1.8))
c = np.array([LONG - CURVE_R, CURVE_R])
mullions = [sg.box(x - 0.05, -1, x + 0.05, 1) for x in np.arange(0.5, LONG - CURVE_R, 1.25)[1:]]
for ang in np.radians([-75, -55, -35]):
    d = np.array([np.cos(ang), np.sin(ang)])
    n = np.array([-d[1], d[0]]) * 0.05
    p0, p1 = c + d * (CURVE_R - 1), c + d * (CURVE_R + 1)
    mullions.append(sg.Polygon([p0 - n, p1 - n, p1 + n, p0 + n]))
ring = ring.difference(unary_union(mullions))
cuts.append(extrude(ring, *RIBBON_Z))
# facade avant : fente vitree, entree vitree (sous l'auvent), porte du fond du passage
cuts += opening("front", 11.3, 13.2, 1.0, 1.5)
cuts += opening("front", 14.65, 16.95, 0, 2.7, panes=3)
cuts.append(box(PORTICO_X1 + 0.4, PASSAGE_X1 - 0.4, 0, ORANGE_D - 0.02, 0, 2.6))   # porte du fond du passage
# pignon gauche : grande baie 4 vantaux a l'etage, porte de service
cuts += opening("left", 0.8, 4.0, 4.0, 6.2, panes=4)
cuts += opening("left", 3.4, 4.2, 0, DOOR_H)
orange = orange - union(cuts)

# ======================= VOLUMES GRIS (bardage) =======================
tall = box(0, LONG, ORANGE_D - 0.1, TALL_Y1, 0, TALL_H)
tall = tall - box(0.2, LONG - 0.2, ORANGE_D + 0.2, TALL_Y1 - 0.2, TALL_H - 0.25, TALL_H + 1)
low = box(0, LONG, TALL_Y1, DEPTH, 0, LOW_H)
low = low - box(0.2, LONG - 0.2, TALL_Y1, DEPTH - 0.2, LOW_H - 0.3, LOW_H + 1)   # terrasse
grey = tall + low

gcuts = []
pitch, gh = 0.3, 0.1                     # bardage : pas 11 mm, rainure 3,75 mm
for z in np.arange(0.4, TALL_H - 0.3, pitch):
    gcuts.append(box(-1, GD, ORANGE_D + 0.05, DEPTH + 1, z, z + gh))              # pignon gauche
    gcuts.append(box(LONG - GD, LONG + 1, ORANGE_D + 0.05, DEPTH + 1, z, z + gh))  # pignon droit
    if z < LOW_H - 0.2:
        gcuts.append(box(-1, LONG + 1, DEPTH - GD, DEPTH + 1, z, z + gh))        # facade arriere
    elif z > LOW_H - 0.25:
        gcuts.append(box(0.2, LONG - 0.2, TALL_Y1 - GD, TALL_Y1 + 0.02, z, z + gh))  # mur terrasse
# facade arriere (photo 3)
gcuts += opening("rear", 17.4, 19.6, 0, SECT_H)             # porte sectionnelle
gcuts += opening("rear", 14.8, 16.7, 0, SECT_H)              # porte ouverte
gcuts += opening("rear", 12.5, 14.4, 0, SECT_H)             # porte sectionnelle
gcuts += opening("rear", 9.8, 11.8, 1.4, 2.1, panes=2)
gcuts += opening("rear", 7.5, 9.4, 1.4, 2.1, panes=2)
gcuts += opening("rear", 6.75, 7.55, 0, DOOR_H)
gcuts += opening("rear", 5.6, 6.5, 0, DOOR_H)
gcuts += opening("rear", 3.9, 4.8, 1.4, 2.1)
gcuts += opening("rear", 2.1, 3.0, 1.4, 2.1)
gcuts += opening("rear", 0.6, 1.6, 0, DOOR_H)
# pignon droit (photo 4)
gcuts += opening("right", 5.0, 5.9, 0, DOOR_H)
gcuts += opening("right", 9.6, 11.5, 0, SECT_H)
gcuts += opening("right", 14.2, 16.1, 1.4, 2.2, panes=2)
# pignon gauche (photos 2 et 6)
gcuts += opening("left", 5.0, 5.9, 0, DOOR_H)
gcuts += opening("left", 9.7, 11.6, 0, SECT_H)
gcuts += opening("left", 11.75, 12.55, 0, DOOR_H)
gcuts += opening("left", 6.8, 7.3, 5.2, 6.0)
grey = grey - union(gcuts)

# ======================= DETAILS SOLIDAIRES =======================
details = [box(0, LONG, SLAB_Y0, 0.1, 0, SLAB_T),                       # trottoir
           box(0, PASSAGE_X1, 0, ORANGE_D - 0.2, 0, SLAB_T)]            # sol portique / passage
for x in [0.25, 2.1, 4.0, 6.1, 8.0]:                                    # colonnes du portique
    details.append(Manifold.cylinder(CEIL_H + 0.05, 0.18).translate((x, 0.25, -0.01)))
details.append(box(14.3, 17.3, -0.6, 0.0, 0, 3.0) - box(14.65, 16.95, -1, 0.1, -0.1, 2.7))  # auvent entree
pz0, pz1 = LOW_H - 0.3, 6.7                                             # pergola terrasse
PG_Y0 = TALL_Y1 + 0.08                  # jeu de 3 mm avec le mur (piece separee)
for x in np.linspace(0.2, LONG - 0.2, 11):
    details.append(box(x - 0.1, x + 0.1, DEPTH - 0.3, DEPTH - 0.1, pz0, pz1))   # poteaux arriere
    details.append(box(x - 0.1, x + 0.1, PG_Y0, PG_Y0 + 0.2, pz0, pz1))         # poteaux cote mur
    details.append(box(x - 0.1, x + 0.1, PG_Y0, DEPTH - 0.1, pz1 - 0.2, pz1))
details.append(box(0.1, LONG - 0.1, DEPTH - 0.3, DEPTH - 0.1, pz1 - 0.2, pz1))
details.append(box(0.1, LONG - 0.1, PG_Y0, PG_Y0 + 0.2, pz1 - 0.2, pz1))

full = union([orange, grey] + details)

# ======================= EVIDEMENT (coque) =======================
foot = orange_plan.union(sg.box(0, ORANGE_D - 0.1, LONG, DEPTH))
walls_in = T + GD
lower_plan = (foot.difference(sg.box(-1, -1, PORTICO_X1, PORTICO_D))
              .difference(sg.box(PORTICO_X1, -1, PASSAGE_X1, ORANGE_D - 0.15)).buffer(-walls_in, join_style=2))
high_plan = foot.intersection(sg.box(-1, -1, LONG + 1, TALL_Y1)).buffer(-walls_in, join_style=2)
low_plan = sg.box(walls_in, TALL_Y1, LONG - walls_in, DEPTH - walls_in)   # le mur de la terrasse descend jusqu au plateau


def stepped_void(plan, z0, z1, top_step=True):
    """Vide extrude ; le haut se resserre en escalier a 45 deg -> rebord de collage sans support."""
    n = 6
    parts = [extrude(plan, z0, z1 - (STEP if top_step else 0))]
    if top_step:
        for i in range(n):
            p = plan.buffer(-STEP * (i + 1) / n, join_style=2)
            if not p.is_empty:
                parts.append(extrude(p, z1 - STEP + STEP * i / n, z1 - STEP + STEP * (i + 1) / n + 1e-4))
    return union(parts)


void = union([
    stepped_void(lower_plan, -1, Z_CUT),
    stepped_void(high_plan, Z_CUT, Z_LID_HIGH),
    stepped_void(low_plan, Z_CUT, Z_LID_LOW),
])
# plafond du portique/passage + rebord de collage sous les pieces du haut
up_all = foot.buffer(-walls_in, join_style=2)
bottom = orange_plan.union(up_all.difference(up_all.buffer(-FLANGE, join_style=2)))
void = void - extrude(bottom, Z_CUT, Z_CUT + PLATE)
# garder un mur d'epaisseur T autour du portique et du passage
keep = [box(x0 - T, x1 + T, y0 - T, y1 + T, z0 - T, z1 + T) for x0, x1, y0, y1, z0, z1 in OPENINGS]
void = void - union(keep)
full = full - void


# ======================= DECOUPE =======================
def label(piece, txt):
    """Grave le numero (en miroir, lisible par-dessous) sur la face inferieure, si la place le permet."""
    z0 = piece.bounding_box()[2]
    reg = cs_to_shapely(piece.slice(z0 + 0.01))
    for hmm in (8.0, 5.0):
        cs, w = text_cs(txt, hmm / K)
        r = np.hypot(w, hmm / K) / 2 + 1.5 / K
        spot = reg.buffer(-r)
        if not spot.is_empty:
            p = spot.representative_point()
            eng = cs.mirror((1, 0)).extrude(0.6 / K).translate((p.x, p.y, z0 - 0.01))
            return piece - eng
    return piece


PLACEMENT = {}   # position de chaque piece dans la maquette assemblee (mm)


def save(man, path):
    mesh = man.to_mesh()
    tm = trimesh.Trimesh(mesh.vert_properties[:, :3] * K, mesh.tri_verts, process=True)
    tm.update_faces(tm.nondegenerate_faces())   # triangles plats -> refuses par certains slicers
    tm.remove_unreferenced_vertices()
    PLACEMENT[os.path.basename(path)] = tm.bounds[0].round(3).tolist()
    tm.apply_translation(-tm.bounds[0])     # pose sur le plateau, origine au coin
    tm.export(path)
    return tm


# zones volontairement plus grandes que le batiment : aucun plan de coupe ne coincide avec une facade
lid_high = box(-5, LONG + 5, -5, DEPTH + 5, Z_LID_HIGH, 50)
lid_low = box(-5, LONG + 5, TALL_Y1 + 0.03, DEPTH + 5, Z_LID_LOW, Z_LID_HIGH)
levels = {
    "B": box(-5, LONG + 5, -5, DEPTH + 5, -1, Z_CUT),                          # murs bas
    "H": box(-5, LONG + 5, -5, DEPTH + 5, Z_CUT, 50) - lid_high - lid_low,     # murs haut
    "T": lid_high,                                                              # toits
    "P": lid_low,                                                               # terrasse + pergola
}
xs = [-1.0] + X_CUTS + [LONG + 1]
ys = [SLAB_Y0 - 1] + Y_CUTS + [DEPTH + 1]
os.makedirs("pieces", exist_ok=True)
os.makedirs("accessoires", exist_ok=True)
report = []
for lv, zone in levels.items():
    part = full ^ zone
    pieces = {}
    for iy in range(len(ys) - 1):
        for ix in range(len(xs) - 1):
            piece = part ^ box(xs[ix], xs[ix + 1], ys[iy], ys[iy + 1], -5, 50)
            if not piece.is_empty():
                pieces[(iy, ix)] = piece
    # les copeaux trop fins sont recolles a la piece voisine de la meme colonne
    for (iy, ix), piece in sorted(pieces.items()):
        b = np.array(piece.bounding_box())
        if min(b[3:] - b[:3]) * K < 8 or piece.volume() * K ** 3 < 3000:
            for n in ((iy - 1, ix), (iy + 1, ix)):
                if n in pieces and pieces[n] is not piece:
                    pieces[n] = pieces[n] + piece
                    pieces[(iy, ix)] = None
                    break
    for (iy, ix), piece in sorted(pieces.items()):
        if piece is None:
            continue
        comps = [cp for cp in piece.decompose() if cp.volume() * K ** 3 > 50]
        comps.sort(key=lambda cp: -cp.volume())
        for j, cp in enumerate(comps):
            pid = f"{ROWS[iy]}{ix + 1}{lv}" + ("" if len(comps) == 1 else "abcdefghijklmnopqrstuvwxyz"[j])
            cp = label(cp, pid)
            tm = save(cp, f"pieces/{pid}.stl")
            report.append((pid, *np.round(tm.extents, 1), round(tm.volume / 1000)))

# ======================= ACCESSOIRES (a plat, a coller) =======================
PANEL_T, TXT_T = 3.0 / K, 0.9 / K


def flat_sign(name, w, h, lines):
    panel = box(-w / 2, w / 2, -h / 2, h / 2, 0, PANEL_T)
    if not lines:
        save(panel, f"accessoires/{name}.stl")
        return
    txt = union([text_cs(t, th, bold)[0].extrude(TXT_T).translate((0, dy, PANEL_T))
                 for t, th, dy, bold in lines])
    # meme origine pour les 2 fichiers -> a charger ensemble comme un objet multi-couleur
    off = np.array(panel.bounding_box()[:3]) * K
    for man, suffix in ((panel, "panneau"), (txt, "lettrage")):
        mesh = man.to_mesh()
        trimesh.Trimesh(mesh.vert_properties[:, :3] * K - off, mesh.tri_verts).export(
            f"accessoires/{name}_{suffix}.stl")


flat_sign("enseigne_PAGAL", 3.9, 1.0, [("PAGAL", 0.42, 0.12, True), ("COLLECTION", 0.13, -0.3, False)])
flat_sign("enseigne_ATELIER", 2.5, 0.6, [("ATELIER", 0.3, 0.0, True)])
flat_sign("enseigne_pignon_droit", 2.8, 1.7, [])
flat_sign("enseigne_pignon_gauche", 2.7, 1.7, [])
# petit auvent de la porte du pignon gauche (prisme a coller au-dessus de la porte)
save(CrossSection([np.array([[0, 0], [0.6, 0], [0, 0.35]])]).extrude(1.0), "accessoires/auvent_porte_gauche.stl")
# eclisses : plaquettes a coller a l'interieur, a cheval sur les joints entre pieces
strips = union([box(0, 30 / K, i * 25 / K, (i * 25 + 20) / K, 0, 1.6 / K) for i in range(8)])
save(strips, "accessoires/eclisses_x8.stl")

print(f"Echelle 1:{1000 / K:.1f}  -  facade {WIDTH_MM:.0f} mm  -  {len(report)} pieces")
print(f"{'piece':6} {'X':>6} {'Y':>6} {'Z':>6}  cm3")
for r in report:
    flag = "" if max(r[1:4]) <= 256 else "  <-- TROP GRAND"
    print(f"{r[0]:6} {r[1]:6} {r[2]:6} {r[3]:6}  {r[4]}{flag}")

with open("pieces/assemblage.json", "w") as f:
    json.dump({k: v for k, v in PLACEMENT.items() if k[0] in ROWS}, f, indent=1)
