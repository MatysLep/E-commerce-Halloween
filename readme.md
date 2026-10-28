# Minuit — E-commerce Halloween

Une boutique de démonstration complète : catalogue, panier, connexion, commande et suivi jusqu’à l’expédition simulée. **Aucun paiement ni envoi physique.**

La solution hybride utilise **EC2 pour l’API** et **Lambda pour les traitements en arrière-plan**. PostgreSQL conserve les commandes et leur historique. Terraform décrit les ressources AWS.

## Essayer en local en une commande

Prérequis : Docker Desktop démarré, ports 8000 et 5432 disponibles.

```bash
docker compose up --build -d
```

Ouvrir **http://localhost:8000**, cliquer sur **Compte démo**, ajouter des produits puis confirmer. Le statut passe de **Confirmée** à **Emballée**, puis **Expédiée**. La page actualise les commandes en cours toutes les cinq secondes. Les emails sont simulés dans les logs du worker.

```bash
docker compose logs -f worker
docker compose down
```

La dernière commande arrête les conteneurs et conserve les données. Le compte local est partagé : il sert uniquement à la démonstration sur votre ordinateur. Le mode AWS impose Cognito et n’accepte pas ce compte.

## Comprendre les dossiers

| Dossier | Explication simple |
| --- | --- |
| [backend](backend/readme.md) | Le cerveau de la boutique : commandes, stock, base et événements. |
| [frontend](frontend/readme.md) | Ce que voit le client dans son navigateur. |
| [infrastructure](infrastructure/readme.md) | Les plans Terraform pour construire l’environnement AWS. |
| [tests](tests/readme.md) | Les vérifications automatiques pour éviter les régressions. |
| [scripts](scripts/readme.md) | Les outils pour préparer et publier une version. |
| [doc](doc/readme.md) | Le sujet, les schémas et les guides détaillés. |
| [.github](.github/readme.md) | Les vérifications exécutées automatiquement sur GitHub. |

Chaque dossier source possède un `readme.md`. Les dossiers générés (`.venv`, `node_modules`, `build`, caches, `.terraform`, `.git`) ne sont pas des dossiers à documenter manuellement ; leurs usages sont expliqués dans les guides.

## Comment une commande circule

1. Le navigateur envoie les produits et quantités, avec une clé identifiant la tentative.
2. L’API vérifie l’utilisateur, recalcule les prix et réserve le stock.
3. Une transaction enregistre **commande + lignes + événement + outbox**. Soit tout est enregistré, soit rien ne l’est.
4. Le client reçoit immédiatement la confirmation après cet enregistrement.
5. Le publisher lit l’outbox, une boîte de départ durable, et envoie l’événement à SNS.
6. SNS distribue les événements aux files SQS. Les Lambdas simulent l’emballage, l’expédition et envoient l’email via SES.
7. Les événements et les reçus de traitement empêchent de répéter une transition déjà terminée.

En local, un worker appelle les mêmes traitements sans services AWS. Il ne reproduit pas le réseau, les délais et les limites de SNS/SQS.

## Développer sans Docker

Python 3.12+, Node.js 24 et Terraform 1.10+ sont nécessaires pour l’ensemble des outils. L’application seule nécessite Python.

```bash
make install
make init
make serve
```

Dans un second terminal, à la racine :

```bash
make worker
```

Ce mode utilise `halloween.db`, une base SQLite locale. Utiliser PostgreSQL pour vérifier les commandes concurrentes. Les variables et les choix de code sont décrits dans [le guide de développement](doc/developpement.md).

## Vérifier le projet

```bash
make install
npm ci
make check
```

Pour inclure les tests PostgreSQL :

```bash
docker compose up -d db
TEST_DATABASE_URL='postgresql+psycopg://halloween:local-only-password@127.0.0.1:5432/halloween' make test
```

Les tests utilisent un schéma SQL temporaire isolé. Sans cette variable, les tests PostgreSQL sont explicitement ignorés. Les tests de concurrence sont volontairement réservés à PostgreSQL.

## Déployer sur AWS

Suivre [le guide de déploiement](doc/deploiement.md). Il indique les prérequis, les commandes, les validations et les frais possibles.

**Le code et les archives sont préparés pour AWS ; aucune ressource AWS n’est déployée par le lancement local.** Un `terraform validate` ou un plan simulé ne prouve pas qu’un déploiement réel fonctionnera dans votre compte. SES, les quotas et les permissions doivent être vérifiés dans ce compte.

Le déploiement utilise l’adresse HTTPS fournie par CloudFront. Aucun achat de domaine ni configuration Route 53 ne sont nécessaires : l’API se trouve derrière un ALB privé relié à une origine VPC CloudFront.

Le mode AWS réduit conserve ALB, NAT et RDS : **il n’est pas gratuit**. Le mode haute disponibilité ajoute une deuxième EC2, RDS Multi-AZ et un NAT par zone. Le budget est une alerte, pas une limite de dépense. La démonstration locale est le choix sans frais AWS.

## Garanties et limites

- Prix en centimes entiers, stock contrôlé en transaction et refus de toute modification du prix par le navigateur.
- Une même clé avec le même panier renvoie la même commande ; un panier différent avec cette clé est refusé.
- Chaque client ne voit que ses commandes. Les jetons Cognito sont vérifiés et l’email doit être confirmé.
- Livraison des messages au moins une fois ; les transitions métier sont dédupliquées en base.
- Un email peut exceptionnellement être envoyé deux fois si le processus s’arrête après SES et avant l’écriture du reçu SQL.
- L’emballage et le transport restent simulés. Un transporteur réel nécessiterait sa propre clé d’idempotence.
- L’architecture d’industrialisation multi-région est une proposition distincte, non incluse dans ce déploiement hybride.

Les procédures de panne, rejeu, sauvegarde et suppression sont dans [le guide d’exploitation](doc/exploitation.md).

Les résultats des contrôles locaux et leurs limites sont consignés dans [le compte rendu de vérification](doc/verifications.md).
