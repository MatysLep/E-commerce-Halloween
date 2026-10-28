# Les tests : vérifier que la boutique tient ses promesses

Les tests Python utilisent pytest. Les mêmes scénarios métier sont exécutés sur SQLite puis, si configuré, sur PostgreSQL.

- `test_orders.py` : montants, réservations de stock, annulation complète d’une transaction, nouvelles tentatives et concurrence.
- `test_api.py` : requêtes HTTP, validation et impossibilité de lire la commande d’un autre client.
- `test_events.py` : chaîne de traitement, répétitions, pannes et réponses partielles SQS.
- `test_auth.py` : vraies signatures RSA de test, expiration, client, émetteur et email vérifié.
- `test_migrations.py` : création d’une base vide et seconde exécution sans perte du stock.
- `cart.test.mjs` : panier et conservation de la clé lors d’une nouvelle tentative navigateur.
- `conftest.py` : préparation et nettoyage des bases temporaires.

```bash
make test
```

Pour les tests de concurrence, démarrer PostgreSQL puis définir `TEST_DATABASE_URL` comme indiqué dans le README principal. Chaque test PostgreSQL crée un schéma au nom aléatoire et ne supprime que ce schéma. Utilisez tout de même une base de test et un compte autorisé à créer des schémas.

Les tests de concurrence sont ignorés sur SQLite car son verrouillage ne reproduit pas celui de PostgreSQL. Les tests simulant AWS ne remplacent pas un essai dans un compte AWS : IAM, réseau, quotas, Cognito et SES doivent aussi être validés après déploiement.
