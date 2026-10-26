# Répétabilité : « serie-1 » contre « serie-2 »

Deux exécutions identiques doivent différer de moins de 10 % ; au-delà, c'est le bruit du poste qui est mesuré, pas le déploiement.

## Trois machines virtuelles

| Utilisateurs | Débit serie-1 | Débit serie-2 | Écart débit | p95 serie-1 (ms) | p95 serie-2 (ms) | Écart p95 | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.9 | 0.9 | +3.8 % | 200 | 182 | -9.0 % | ok |
| 10 | 7.4 | 8.3 | +13.1 % | 625 | 689 | +10.2 % | **hors tolérance** |
| 25 | 8.0 | 9.5 | +17.8 % | 3121 | 3310 | +6.1 % | **hors tolérance** |
| 50 | 1.7 | 2.5 | +42.7 % | 4629 | 5749 | +24.2 % | **hors tolérance** |
| 100 | 3.3 | 2.3 | -31.3 % | 11920 | 7115 | -40.3 % | **hors tolérance** |
| 150 | 4.2 | 1.8 | -58.8 % | 30031 | 10011 | -66.7 % | **hors tolérance** |

## Trois conteneurs

| Utilisateurs | Débit serie-1 | Débit serie-2 | Écart débit | p95 serie-1 (ms) | p95 serie-2 (ms) | Écart p95 | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.0 | 0.9 | -5.1 % | 78 | 71 | -9.0 % | ok |
| 10 | 9.6 | 9.8 | +2.1 % | 84 | 83 | -1.2 % | ok |
| 25 | 23.7 | 23.6 | -0.1 % | 107 | 108 | +0.9 % | ok |
| 50 | 45.7 | 45.8 | +0.1 % | 309 | 335 | +8.4 % | ok |
| 100 | 53.5 | 55.2 | +3.2 % | 2303 | 2247 | -2.4 % | ok |
| 150 | 52.1 | 53.1 | +1.9 % | 4601 | 4520 | -1.8 % | ok |
