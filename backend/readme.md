# Le backend : le cerveau de la boutique

Ce dossier contient le code Python exécuté sur le serveur. Il vérifie les commandes et enregistre les informations dans la base.

- [`shop`](shop/readme.md) : l’API et la logique partagée avec les Lambdas.
- [`migrations`](migrations/readme.md) : l’historique des changements de structure de la base.

Le même code métier est utilisé en local et sur AWS. On change les connexions et les points d’entrée, pas les règles de commande.

Depuis la racine : `make init`, puis `make serve` et, dans un autre terminal, `make worker`. Avec Docker, `docker compose up --build -d` lance tout.

La documentation interactive de l’API se trouve à `http://localhost:8000/api/docs`.
