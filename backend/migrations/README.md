# Les migrations : faire évoluer la base

Une migration explique comment créer ou modifier des tables. Alembic mémorise la version appliquée afin de ne pas rejouer les changements inutilement.

- `env.py` utilise la connexion fournie par l’outil d’administration.
- `script.py.mako` est le modèle pour générer une nouvelle migration.
- [`versions`](versions/README.md) contient les changements numérotés.

En local, `make init` applique les migrations et ajoute les produits manquants. Sur AWS, une Lambda d’administration les applique avant le démarrage de l’API. Un verrou PostgreSQL empêche deux migrations simultanées.

Ne modifiez pas une migration déjà déployée : ajoutez une nouvelle version. Une mise à jour doit rester compatible avec l’ancienne API pendant le remplacement progressif des EC2. Sauvegardez avant un changement destructif et testez la restauration.
