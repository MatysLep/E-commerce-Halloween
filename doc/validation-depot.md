# Validation du dépôt au 30 octobre 2026

Cette session vérifie la cohérence du dépôt après sa révision documentaire. Elle ne réalise aucun déploiement AWS et ne remplace pas les [essais cloud historiques](rapport-tests-api.md).

| Contrôle exécuté | Résultat |
| --- | --- |
| pytest sans PostgreSQL configuré | 56 réussis, 38 ignorés |
| pytest avec PostgreSQL local | 90 réussis, 4 ignorés |
| Tests Node.js | 3 réussis |
| Ruff et Prettier | Réussis |
| Syntaxe JavaScript et format Terraform | Réussis |
| Présence des README | 15 dossiers source documentés |
| `terraform validate` | Configuration valide |
| `terraform test` | 8 scénarios réussis, fournisseurs simulés |
| `docker compose config --quiet` | Configuration valide |
| Reconstruction de l’image Docker | Non terminée : attente bloquée des métadonnées `python:3.12-slim`, puis arrêt du contrôle |

Les quatre cas ignorés avec PostgreSQL configuré concernent la concurrence sur SQLite, dont le verrouillage ne reproduit pas PostgreSQL. Leurs variantes PostgreSQL sont exécutées. Un avertissement de dépréciation Starlette/HTTPX subsiste, sans échec de test. Le scénario Terraform ciblant les permissions SES produit un avertissement attendu sur l’utilisation de `-target` ; il ne remplace pas les plans complets également exécutés.

## Correction de cohérence Terraform

Le premier passage a identifié une attente obsolète dans `architecture.tftest.hcl` : le scénario `high_availability=true` exigeait encore RDS Multi-AZ, `db.t4g.small`, gp3 et sept jours de sauvegardes. Le code `database.tf` et le schéma récent conservent RDS Single-AZ, `db.t4g.micro`, gp2 et un jour de sauvegardes dans les deux modes.

Le scénario, renommé `compute_redundancy_plan`, vérifie désormais la redondance EC2/NAT et le maintien du profil SQL réduit. La description de variable et les guides ont été corrigés. Aucune ressource Terraform n’a été modifiée : cette correction ne met pas en place de haute disponibilité SQL.

## Hygiène du dépôt

- Noms des 15 README normalisés et liens internes adaptés.
- README principal réécrit avec contexte, alternatives, deux architectures documentées, stack, installation et apprentissages.
- Rapport académique et source Markdown ajoutés dans `doc/`.
- Exclusions Git complétées pour les variantes de configuration, bases locales et fichiers temporaires.
- Contexte Docker limité aux fichiers utiles à la construction de l’application.
- Fichiers `.DS_Store` supprimés à la racine et dans `doc/`.
- Bases, dépendances locales, états et sauvegardes Terraform conservés hors suivi Git.

## Reproduire

```bash
make lint
TEST_DATABASE_URL='postgresql+psycopg://halloween:local-only-password@127.0.0.1:5432/halloween' make test
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure test
```

Les résultats ne mesurent ni la charge, ni la restauration, ni la bascule multi-région. La présence des artefacts et les contrôles statiques ne remplacent pas une validation du compte cible avant déploiement.
