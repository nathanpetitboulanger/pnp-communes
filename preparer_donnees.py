"""Préparation des données et génération du PMTiles pour le TP « Portrait des communes du Parc ».

À lancer depuis le dossier du TP (ou n'importe où) :
    uv run python preparer_donnees.py
"""

import subprocess
from pathlib import Path

import geopandas as gpd

DOSSIER = Path(__file__).resolve().parent
DONNEES = DOSSIER / "donnees"
GPKG_SORTIE = DONNEES / "communes_parc.gpkg"
PMTILES_SORTIE = DONNEES / "communes_parc.pmtiles"

# Seuil d'exclusion des éclats topologiques (en % de la surface communale)
SEUIL_PCT = 1.0


def main() -> None:
    # 0. Nettoyage des fichiers produits par un lancement précédent
    GPKG_SORTIE.unlink(missing_ok=True)
    PMTILES_SORTIE.unlink(missing_ok=True)

    # 1. Lecture des données sources
    #    - communes (tracé généralisé, EPSG:2154) : pour l'affichage web
    #    - communes_precis (pleine précision, EPSG:2154) : pour les calculs de surface
    #    - cœur et aire d'adhésion (EPSG:4326) : reprojetés en EPSG:2154 (mètres)
    com_gen = gpd.read_file(DONNEES / "communes_64_65.gpkg", layer="communes")
    com_pre = gpd.read_file(DONNEES / "communes_64_65.gpkg", layer="communes_precis")
    coeur_4326 = gpd.read_file(DONNEES / "pnp_coeur.geojson")
    aire_4326 = gpd.read_file(DONNEES / "pnp_aire_adhesion.geojson")

    coeur_2154 = coeur_4326.to_crs(2154)
    aire_2154 = aire_4326.to_crs(2154)

    geom_coeur = coeur_2154.geometry.union_all()
    geom_aire = aire_2154.geometry.union_all()
    geom_parc = geom_coeur.union(geom_aire)

    # 2. Contrôle comparatif : intersection sur tracé précis vs généralisé
    n_int_pre = int(com_pre.intersects(geom_parc).sum())
    n_int_gen = int(com_gen.intersects(geom_parc).sum())

    # 3. Calcul des surfaces et parts sur le tracé à pleine précision (EPSG:2154)
    df = com_pre[com_pre.intersects(geom_parc)].copy()
    surf_tot_km2 = df.geometry.area / 1e6
    coeur_km2 = df.geometry.intersection(geom_coeur).area / 1e6
    aire_km2 = df.geometry.intersection(geom_aire).area / 1e6
    parc_km2 = df.geometry.intersection(geom_parc).area / 1e6

    df["pct_coeur_brut"] = 100.0 * coeur_km2 / surf_tot_km2
    df["pct_aire_brut"] = 100.0 * aire_km2 / surf_tot_km2
    df["pct_parc_brut"] = 100.0 * parc_km2 / surf_tot_km2

    # Séparation entre éclats topologiques (<= 0,0094 %) et vraies communes (>= 11,81 %)
    eclats = df[df["pct_parc_brut"] < SEUIL_PCT]
    retenues = df[df["pct_parc_brut"] >= SEUIL_PCT].copy()

    # Neutralisation des éclats internes (ex. Saint-Lary-Soulan à 0,000007 % en cœur)
    en_coeur = retenues["pct_coeur_brut"] >= SEUIL_PCT
    en_aire = retenues["pct_aire_brut"] >= SEUIL_PCT

    retenues["pct_coeur"] = retenues["pct_coeur_brut"].where(en_coeur, 0.0).round(1)
    retenues["pct_aire"] = retenues["pct_aire_brut"].where(en_aire, 0.0).round(1)
    retenues["pct_parc"] = retenues["pct_parc_brut"].round(1)
    retenues["coeur_km2"] = (
        (coeur_km2.loc[retenues.index]).where(en_coeur, 0.0).round(2)
    )
    retenues["aire_km2"] = (aire_km2.loc[retenues.index]).where(en_aire, 0.0).round(2)

    def classer_statut(row) -> str:
        c = row["pct_coeur"] > 0
        a = row["pct_aire"] > 0
        if c and a:
            return "Cœur et aire d'adhésion"
        if c:
            return "Cœur uniquement"
        return "Aire d'adhésion uniquement"

    retenues["statut"] = retenues.apply(classer_statut, axis=1)

    # 4. Jointure des indicateurs sur les géométries généralisées (affichage web)
    colonnes_calc = [
        "code_insee",
        "pct_coeur",
        "pct_aire",
        "pct_parc",
        "coeur_km2",
        "aire_km2",
        "statut",
    ]
    communes_poly = com_gen.merge(retenues[colonnes_calc], on="code_insee", how="inner")

    # 5. Couche de points pour les cercles proportionnels (population)
    #    representative_point() garantit un point à l'intérieur de chaque polygone
    #    (contrairement à centroid, qui sort de 3 communes)
    cent_ok = int(communes_poly.geometry.centroid.within(communes_poly.geometry).sum())
    pts_geom = communes_poly.geometry.representative_point()
    rep_ok = int(pts_geom.within(communes_poly.geometry).sum())
    assert rep_ok == len(communes_poly), (
        "Un point représentatif est hors de sa commune !"
    )

    communes_pts = communes_poly.copy()
    communes_pts["geometry"] = pts_geom
    # Trier par population décroissante : les petits cercles se dessinent au-dessus des grands
    communes_pts = communes_pts.sort_values("population", ascending=False).reset_index(
        drop=True
    )

    # 6. Export en GeoPackage (reprojeté en EPSG:4326 pour les tuiles vectorielles)
    communes_poly_4326 = communes_poly.to_crs(4326)
    communes_pts_4326 = communes_pts.to_crs(4326)

    communes_poly_4326.to_file(GPKG_SORTIE, layer="communes")
    communes_pts_4326.to_file(GPKG_SORTIE, layer="communes_points")
    coeur_4326.to_file(GPKG_SORTIE, layer="coeur")
    aire_4326.to_file(GPKG_SORTIE, layer="aire")

    # 7. Conversion en PMTiles par ogr2ogr (-preserve_fid requis pour feature-state)
    subprocess.run(
        [
            "ogr2ogr",
            "-f",
            "PMTiles",
            str(PMTILES_SORTIE),
            str(GPKG_SORTIE),
            "-dsco",
            "MINZOOM=6",
            "-dsco",
            "MAXZOOM=14",
            "-preserve_fid",
        ],
        check=True,
    )

    # 8. Contrôles de qualité (reproduisibles pour le README)
    poids_ko = PMTILES_SORTIE.stat().st_size / 1024
    ouest, sud, est, nord = communes_poly_4326.total_bounds

    print("=== CONTRÔLES DE PRÉPARATION ===")
    print(f"Intersections (précis / généralisé) : {n_int_pre} / {n_int_gen}")
    print(
        f"Éclats écartés (< {SEUIL_PCT} %) : {len(eclats)} "
        f"(max = {eclats['pct_parc_brut'].max():.4f} %)"
    )
    print(
        f"Communes retenues (>= {SEUIL_PCT} %) : {len(communes_poly)} "
        f"(min = {retenues['pct_parc_brut'].min():.2f} %)"
    )
    print("Répartition par statut :", communes_poly["statut"].value_counts().to_dict())
    print(
        f"Population (INSEE {communes_poly['date_population'].iloc[0]}) : "
        f"total = {int(communes_poly['population'].sum()):,} hab. | "
        f"min = {int(communes_poly['population'].min())} | "
        f"médiane = {int(communes_poly['population'].median())} | "
        f"max = {int(communes_poly['population'].max())}"
    )
    print(
        f"Points dans leur commune : centroid = {cent_ok}/{len(communes_poly)}, "
        f"representative_point = {rep_ok}/{len(communes_poly)}"
    )
    print(f"Emprise (WGS84) : [[{ouest:.3f}, {sud:.3f}], [{est:.3f}, {nord:.3f}]]")
    print(f"PMTiles généré : {PMTILES_SORTIE.name} ({poids_ko:.1f} Ko)")

    print("\n=== CONTRÔLE DU TUILAGE (zoom par zoom) ===")
    print(f"{'Zoom':>4} | {'Polygones (uniques)':>19} | {'Points (uniques)':>16}")
    print("-" * 46)
    for zoom in range(6, 15):
        poly_z = gpd.read_file(PMTILES_SORTIE, layer="communes", ZOOM_LEVEL=zoom)
        pts_z = gpd.read_file(PMTILES_SORTIE, layer="communes_points", ZOOM_LEVEL=zoom)
        print(
            f"{zoom:>4} | {poly_z['code_insee'].nunique():>12} / {len(communes_poly):<4} | "
            f"{pts_z['code_insee'].nunique():>9} / {len(communes_pts)}"
        )


if __name__ == "__main__":
    main()
