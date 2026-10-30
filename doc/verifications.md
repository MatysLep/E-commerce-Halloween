# Historique des vérifications

## Lecture des résultats

Le bilan ci-dessous décrit la session locale du 28 octobre. Les essais AWS du 29 octobre sont consignés dans [le rapport API](rapport-tests-api.md). Les contrôles du 30 octobre sont présentés dans [la validation du dépôt](validation-depot.md). Ces sessions ont des périmètres et des versions différents : leurs nombres de tests ne se cumulent pas.

## Session du 28 octobre 2026

## Résultats observés

| Vérification | Résultat |
| --- | --- |
| Python : API, métier, authentification, migrations, événements | **61 tests réussis** avec SQLite et PostgreSQL. |
| Concurrence SQLite | 4 cas volontairement ignorés ; leurs équivalents PostgreSQL ont réussi. |
| JavaScript : panier, montants, nouvelle tentative | **3 tests réussis**. |
| Terraform | Configuration valide ; **2 plans simulés réussis**, modes réduit et haute disponibilité. |
| Style Python, JavaScript et CSS | Ruff et Prettier réussis. |
| Documentation | Un `README.md` dans chacun des **13 dossiers source**. |
| Docker Compose | PostgreSQL sain, migrations terminées, API et worker démarrés. |
| Navigateur | Compte démo, ajout au panier, commande confirmée, panier vidé et historique jusqu’à l’expédition simulée. |
| Archive Lambda | Imports et migration sur une base SQLite en mémoire réussis dans l’image officielle `public.ecr.aws/lambda/python:3.12`, architecture Linux x86_64. |

La capture `demonstration-locale.png` montre l’historique du parcours testé. Cette commande est une donnée de démonstration locale, pas une vente réelle.

Le contrôle du runtime Lambda vérifie notamment la compatibilité des bibliothèques binaires, la présence du code et celle des migrations. L’archive décompressée représente environ 87 Mio, sous la limite de taille d’archive Lambda utilisée par cette solution.

## Ce qui n’avait pas été exécuté le 28 octobre

Lors de cette session du 28 octobre, aucun `terraform apply` sur AWS, aucune création de ressource cloud et aucun envoi SES réel n’ont été effectués. La session Cognito réelle, les permissions IAM du compte, les quotas, le réseau AWS, les alarmes livrées par email et la restauration RDS restent à tester après déploiement.

Les tests Python signalent un avertissement de dépréciation du TestClient Starlette avec HTTPX. Cela n’affecte pas leurs résultats ; la dépendance de test devra être adaptée lors d’une prochaine mise à jour.

La configuration Terraform a ensuite été adaptée à un déploiement sans domaine personnalisé : ALB interne, origine VPC CloudFront et certificat HTTPS par défaut CloudFront. Les plans simulés vérifient aussi ces propriétés, sans variables Route 53 ni certificat ACM personnalisé. Ils vérifient les trois destinataires d’alertes de l’équipe ; la livraison réelle des emails reste à tester après déploiement.

## Reproduire les contrôles

```bash
make install
npm ci
docker compose up -d db
make lint
TEST_DATABASE_URL='postgresql+psycopg://halloween:local-only-password@127.0.0.1:5432/halloween' make test
make build
terraform -chdir=infrastructure init -backend=false -input=false
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure test
docker compose up --build -d
```

Les tests PostgreSQL créent puis suppriment leurs propres schémas temporaires. Les tests Terraform utilisent des fournisseurs simulés, sans accès au compte AWS. La boutique locale reste disponible sur `http://localhost:8000` après la dernière commande.
