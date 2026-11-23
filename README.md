# Portrait des communes du Parc national des Pyrénées

Carte interactive réalisée dans le cadre du TP individuel de l'UE902-1 (*Webmapping*). Elle présente, commune par commune, les 69 communes ayant du territoire dans le Parc national des Pyrénées (cœur et/ou aire d'adhésion), leur population municipale et la part de leur surface située en cœur de parc.

## Reproduire les données

```sh
uv run python preparer_donnees.py
```

Le script lit les fichiers sources dans `donnees/` (`communes_64_65.gpkg`, `pnp_coeur.geojson`, `pnp_aire_adhesion.geojson`), calcule les indicateurs et produit `donnees/communes_parc.pmtiles` via `ogr2ogr` (GDAL ≥ 3.8).

---

## 1. Choix

- **Sélection des communes (règle du seuil à 1 %)** : les intersections et surfaces sont calculées dans le système métrique Lambert-93 (`EPSG:2154`, après reprojection du cœur et de l'aire d'adhésion depuis `EPSG:4326`) sur la couche à pleine précision `communes_precis`. Parmi les 107 communes qui intersectent géométriquement le Parc, 38 ne le touchent que par un éclat topologique de bordure (au plus `0,0094 %` de leur surface, soit moins de 920 m²), tandis que la suivante (*Lescun*) en compte `11,81 %`. Retenir les communes ayant **au moins 1 % de leur surface dans le Parc** sélectionne sans ambiguïté **69 communes** (18 dans les Pyrénées-Atlantiques, 51 dans les Hautes-Pyrénées). Le même seuil de `1 %` neutralise les éclats internes (comme *Saint-Lary-Soulan*, à `0,000007 %` en cœur).
- **Géométries d'affichage** : les indicateurs calculés sur `communes_precis` sont joints à la couche généralisée `communes` (21 139 sommets au lieu de 738 133) afin d'alléger les tuiles vectorielles.
- **Part en cœur de parc (un taux → choroplèthe en aplats)** : représentée par une gamme séquentielle verte en **4 classes manuelles** (`0 %` pour les 55 communes d'aire d'adhésion seule, puis `1 à 20 %`, `20 à 40 %`, `40 % et plus` pour les 14 communes en cœur). Un découpage automatique par quantiles aurait échoué à cause des 55 valeurs nulles. Les aplats sont glissés sous les écritures du Plan IGN afin de garder les noms de lieux lisibles.
- **Population municipale (un effectif → cercles proportionnels)** : représentée par des cercles orange placés sur `representative_point()` (garanti à l'intérieur de chaque commune), triés par population décroissante pour que les petits cercles restent cliquables par-dessus les grands. L'œil comparant des surfaces, le rayon suit `r = 0,3 × √population` (exactement reproduit à l'échelle 1:1 dans la légende SVG).
- **Fond de carte et lecture sur téléphone** : fond **Plan IGN gris** pour ne pas concurrencer les verts choroplèthes et les cercles orange ; panneau de légende replié par défaut sous `640 px` de largeur ; fiche commune complète au clic ou au toucher.

---

## 2. Contrôles

Tous les contrôles suivants sont affichés à chaque lancement de `preparer_donnees.py` :

- **Précis vs généralisé** : `107` communes intersectent le Parc sur `communes_precis`, contre `112` sur `communes` (5 faux positifs dus à la généralisation, évités grâce au calcul sur `communes_precis`).
- **Séparation éclats / communes du Parc** : `38` éclats écartés (`max = 0,0094 %`), `69` communes retenues (`min = 11,81 %`).
- **Répartition par statut** : `55` communes en *Aire d'adhésion uniquement*, `10` en *Cœur et aire d'adhésion*, `4` en *Cœur uniquement* (*Lescun*, *Aragnouet*, *Laruns*, *Urdos*).
- **Population municipale (INSEE `2022-01-01`)** : total = `31 164 hab.`, min = `19` (*Viey*), médiane = `186`, max = `7 060` (*Bagnères-de-Bigorre*).
- **Placement des symboles** : `centroid` tombe hors du polygone pour `3` communes (*Accous*, *Bagnères-de-Bigorre*, *Vignec*, soit `66/69`) ; `representative_point()` place **`69/69`** points à l'intérieur de leur commune.
- **Tuilage PMTiles (`communes_parc.pmtiles`, `852,8 Ko`)** : contrôle zoom par zoom de `6` à `14` via GeoPandas (`ZOOM_LEVEL`) → **`69/69`** polygones uniques et **`69/69`** points uniques présents à chaque niveau de zoom.
- **Affichage et console** : vérifié sur serveur local (`serveur.py`, requêtes par plage HTTP 206), sur écran large et en vue téléphone, sans erreur ni avertissement dans la console.

---

## 3. Limites

- **Population communale ≠ habitants vivant dans le Parc** : la population affichée est la *population municipale totale* de la commune (INSEE 2022), et non le nombre d'habitants résidant à l'intérieur du périmètre du Parc. Par exemple, *Bagnères-de-Bigorre* compte `7 060` habitants, mais seulement `31,2 %` de sa surface (la partie montagneuse, peu peuplée) est en aire d'adhésion : la carte surestime donc visuellement la population réellement présente dans le Parc. Pour répondre à la question « combien d'habitants vivent dans le Parc ? », il faudrait croiser le périmètre du Parc avec les **données carroyées Filosofi de l'INSEE (carreaux de 200 m)** (ou le bâti résidentiel de la BD TOPO ventilé à la population) afin de cartographier directement la densité d'habitants par carreau dans le Parc.
- **Décalage de millésimes** : les limites communales datent d'ADMIN EXPRESS 2026, le périmètre du Parc de septembre 2024 (DREAL Nouvelle-Aquitaine) et la population municipale du 1er janvier 2022.
- **Superposition de cercles aux petits zooms** : dans les vallées denses en petites communes (Lavedan, vallée d'Argelès), quelques cercles se touchent au cadrage d'ouverture et demandent un léger zoom pour être isolés confortablement au doigt.

---

## 4. Journal de bord

1. Lecture du `LISEZMOI.txt` et inspection des couches : repérage du mélange de CRS (`EPSG:2154` pour les communes, `EPSG:4326` pour le Parc) → reprojection systématique du Parc en `EPSG:2154` avant tout calcul de surface.
2. Comparaison des intersections entre `communes_precis` (107) et `communes` (112) : mise en évidence de 5 faux positifs liés au tracé généralisé → décision de faire tous les calculs sur `communes_precis`.
3. Classement des parts de surface dans le Parc : découverte de 38 éclats topologiques (`≤ 0,0094 %`) suivis d'un saut brutal à `11,81 %` (*Lescun*), plus un éclat interne sur *Saint-Lary-Soulan* (`0,000007 %` en cœur) → mise en place du seuil propre à `1 %`.
4. Examen de la distribution de `pct_coeur` : 55 communes sur 69 sont à `0 %`, ce qui casse les quantiles automatiques → choix de 4 classes manuelles équilibrées (`0 %`, `1–20 %`, `20–40 %`, `≥ 40 %`).
5. Contrôle du placement des cercles : `.centroid` sortait de 3 communes en forme de croissant (*Accous*, *Bagnères-de-Bigorre*, *Vignec*) → remplacement par `.representative_point()` (`69/69` dedans).
6. Conversion en PMTiles avec `ogr2ogr` : ajout de `-preserve_fid` pour que le survol par `feature-state` fonctionne dans MapLibre, et contrôle zoom par zoom (`69/69` entités conservées partout).
7. Adaptation mobile de `index.html` : passage au fond Plan IGN `gris` pour le contraste, légende `<details>` repliée automatiquement sur téléphone, et vérification complète dans le navigateur.
