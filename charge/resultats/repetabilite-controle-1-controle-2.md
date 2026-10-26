# Répétabilité : « controle-1 » contre « controle-2 »

Deux exécutions identiques doivent différer de moins de 10 % ; au-delà, c'est le bruit du poste qui est mesuré, pas le déploiement.

## Trois conteneurs

| Utilisateurs | Débit controle-1 | Débit controle-2 | Écart débit | p95 controle-1 (ms) | p95 controle-2 (ms) | Écart p95 | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.0 | 0.9 | -5.0 % | 71 | 68 | -4.2 % | ok |
| 10 | 9.8 | 9.5 | -2.4 % | 75 | 75 | +0.0 % | ok |
| 25 | 23.9 | 23.9 | -0.3 % | 115 | 123 | +7.0 % | ok |
| 50 | 45.8 | 46.7 | +2.1 % | 326 | 259 | -20.6 % | **hors tolérance** |
| 100 | 55.1 | 46.7 | -15.3 % | 2254 | 4060 | +80.1 % | **hors tolérance** |
| 150 | 52.9 | 43.2 | -18.2 % | 4483 | 6116 | +36.4 % | **hors tolérance** |
