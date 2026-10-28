# Développer la solution hybride

## Choix de structure

Le backend utilise Python 3.12, FastAPI pour HTTP, SQLAlchemy pour SQL et Alembic pour les migrations. Le frontend utilise les fonctions standard du navigateur. Les versions des dépendances sont fixées dans `requirements.txt` et `package-lock.json`.

La séparation est volontairement simple : règles dans `domain.py` et `orders.py`, accès SQL dans `models.py` et `database.py`, points d’entrée dans `api.py` et `handlers.py`. Une fonction courte et explicite est préférable à une abstraction sans besoin concret. On partage la logique des traitements entre l’exécution locale et AWS.

Les paramètres de connexion et les fonctions d’envoi sont injectés dans les cas d’usage. Cela rend les tests lisibles : on peut remplacer SNS par une fonction qui échoue et vérifier que l’événement n’est pas perdu.

## Trois façons de travailler

| Mode | Données | Connexion | Traitements |
| --- | --- | --- | --- |
| Python local | SQLite dans `halloween.db` | Compte démo | Worker local |
| Docker local | PostgreSQL 16 persistant | Compte démo | Worker local |
| AWS | PostgreSQL 16 RDS | Cognito | EC2 publisher, SNS/SQS, Lambdas et SES |

Le mode Python est pratique pour lire et modifier le code. Docker est recommandé pour démontrer la solution et vérifier les transactions réelles. SQLite ne prouve pas la sûreté des verrous PostgreSQL.

## Commandes usuelles

Toutes les commandes se lancent à la racine.

```bash
make install
npm ci
make init
make serve
# Dans un second terminal :
make worker
```

Pour modifier le code avec PostgreSQL local :

```bash
docker compose up -d db
export APP_ENV=local
export DATABASE_URL='postgresql+psycopg://halloween:local-only-password@127.0.0.1:5432/halloween'
make init
make serve
```

Définir la même variable dans le terminal du worker. Ne lancez pas en même temps `make serve` et le conteneur API sur le port 8000. Pour changer le port Docker, adapter uniquement le port à gauche de la correspondance dans `compose.yaml`.

`.env.example` est un aide-mémoire : le code ne charge pas automatiquement `.env`. Les variables doivent être exportées ou transmises par Docker/systemd. Ne placez jamais de secret AWS dans la configuration du frontend.

## Configuration

| Variable | Utilité |
| --- | --- |
| `APP_ENV` | `local`, `test` ou `aws`. Le mode AWS interdit les réglages SQL locaux implicites. |
| `DATABASE_URL` | Adresse SQL locale. Ignorée en mode AWS. |
| `AWS_REGION` | Région des clients AWS, Paris par défaut. |
| `DB_HOST`, `DB_NAME` | Serveur et nom de base RDS. |
| `DB_SECRET_ARN` | Secret du compte SQL utilisé par ce processus. |
| `DB_CA_BUNDLE` | Fichier des autorités publiques RDS pour vérifier TLS. |
| `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` | Identifiants de la connexion Cognito. |
| `EVENT_TOPIC_ARN` | Topic SNS auquel le publisher envoie les événements. |
| `CONSUMER` | `packing`, `shipping` ou `notification` dans les Lambdas métier. |
| `SES_SENDER_EMAIL` | Adresse d’envoi validée dans SES. |
| `APP_DB_SECRET_ARN` | Réservé à la Lambda de migration pour préparer le compte SQL limité. |

Terraform transmet les variables AWS. Les secrets SQL sont lus depuis Secrets Manager à l’ouverture d’une nouvelle connexion. Les pools sont limités à deux connexions par processus et recyclés régulièrement.

## API disponible

| Méthode et chemin | Besoin |
| --- | --- |
| `GET /api/health` | Vérifier que l’API atteint SQL. |
| `GET /api/products` | Afficher le catalogue. |
| `GET /api/me` | Vérifier sa session. |
| `POST /api/orders` | Commander ; en-tête `Idempotency-Key` obligatoire. |
| `GET /api/orders?limit=20&offset=0` | Lister ses commandes avec pagination. |
| `GET /api/orders/{id}` | Lire sa commande et son historique. |

Exemple local :

```bash
curl -X POST http://localhost:8000/api/orders \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer local-demo' \
  -H 'Idempotency-Key: demonstration-0001' \
  -d '{"items":[{"product_id":"citrouille","quantity":2}]}'
```

Rejouer exactement cette requête doit renvoyer le même identifiant. Changer le panier avec la même clé renvoie `409`. Retirer la connexion renvoie `401`. Ajouter un prix au JSON renvoie `422`. Les données non autorisées d’une autre personne ne sont jamais renvoyées.

## Ajouter une règle ou un traitement

1. Définir le comportement métier et son erreur attendue.
2. Modifier la fonction qui possède cette responsabilité, sans ajouter la règle dans le JavaScript seul.
3. Ajouter un test de résultat observable, notamment pour les échecs et les nouvelles tentatives.
4. Si la base change, créer une nouvelle migration ; ne pas réécrire `0001` après déploiement.
5. Exécuter `make check`, puis les tests PostgreSQL.

Pour créer une migration automatiquement pendant le développement, utiliser l’API Alembic avec une connexion vers votre base locale et `target_metadata` de `shop.models.Base`, comme le fait `env.py`. Relire systématiquement les opérations générées ; elles ne connaissent pas les règles de conservation des données.

## Format et qualité

```bash
.venv/bin/ruff check backend scripts tests
.venv/bin/ruff format backend scripts tests
npm run format
make check
```

Les logs permettent de rapprocher les opérations avec `order_id` et `event_id`. Les réponses SQL inattendues ne dévoilent pas la requête ou le mot de passe. La validation du corps interdit les champs supplémentaires pour éviter qu’un client puisse imposer un prix ou un propriétaire.
