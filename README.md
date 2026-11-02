# Minuit — E-commerce Halloween

Boutique pédagogique réalisée à **IMT Nord Europe**, dans le module **Infrastructures cloud et virtualisation — FISA TI 2027**.

**Équipe :** Bahir Boudouma Lambarki, Tarik Fellahi et Matys Lepretre.

Minuit propose un catalogue Halloween, un panier, des comptes clients et le suivi des commandes. L’emballage et l’expédition sont simulés ; aucun paiement ni envoi physique n’est effectué.

## Lancer l’application

Avec Docker et Docker Compose installés, depuis la racine du dépôt :

```bash
docker compose up --build -d
```

Ouvrir **http://localhost:8000**, choisir **Compte démo** ou créer un compte, puis passer une commande. La documentation de l’API est disponible sur **http://localhost:8000/api/docs**. Les ports 8000 et 5432 doivent être libres.

```bash
docker compose logs -f worker  # Traitements et emails simulés
docker compose down           # Arrêt ; les données PostgreSQL sont conservées
```

## Développement local

Prérequis : Python 3.12+, Make et Node.js 24 pour les outils frontend.

```bash
make install
npm ci
make init
make serve
```

Dans un second terminal :

```bash
make worker
```

Ce mode utilise SQLite dans `halloween.db`. Les variables disponibles sont indiquées dans [`.env.example`](.env.example) ; elles doivent être exportées dans le terminal, car l’application ne charge pas automatiquement ce fichier.

## Organisation

| Dossier | Contenu |
| --- | --- |
| `backend/` | API FastAPI, logique métier, notifications et migrations SQL |
| `frontend/` | Pages HTML, styles, JavaScript et images du catalogue |
| `infrastructure/` | Infrastructure AWS et tests Terraform |
| `scripts/` | Construction des archives et publication du frontend |
| `tests/` | Tests Python et JavaScript |
| `doc/architecture/` | Les deux schémas d’architecture PNG |
| `.github/workflows/` | Validation continue |

## Architectures et livrables

### Architecture hybride réalisée

![Architecture hybride AWS](doc/architecture/architecture-aws-hybride.png)

CloudFront distribue le frontend depuis S3 et transmet les appels API à un ALB interne, qui dessert FastAPI sur EC2. RDS PostgreSQL conserve les données, Cognito gère les comptes et SNS/SQS alimentent les traitements Lambda. SES envoie les emails.

Le mode réduit utilise une EC2 et un NAT. `high_availability=true` augmente la capacité EC2 et le nombre de NAT ; RDS reste Single-AZ.

### Cible d’industrialisation

![Architecture industrialisée](doc/architecture/architecture-aws-industrialisation.png)

Cette proposition ajoute notamment Aurora PostgreSQL, RDS Proxy, un cache, Step Functions et un environnement de secours. Elle n’est pas déployée par le code Terraform du dépôt.

- [Présentation PowerPoint](PresentationInfraCloud.pptx)
- [Rapport PDF](Rapport.pdf)
- [Rapport Word](Rapport.docx)

## Déploiement AWS

Prérequis : un compte AWS, les identifiants d’un profil AWS configuré, Terraform 1.10+ et l’environnement de développement installé. Le déploiement crée des ressources payantes, notamment NAT, ALB et RDS.

```bash
make check
make build
test -f infrastructure/terraform.tfvars || cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
```

Renseigner le profil AWS, l’identifiant du compte, l’expéditeur SES et les destinataires d’alertes dans `infrastructure/terraform.tfvars`, puis :

```bash
terraform -chdir=infrastructure init
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure test
terraform -chdir=infrastructure plan -out=deployment.tfplan
```

Après examen du plan :

```bash
terraform -chdir=infrastructure apply deployment.tfplan
.venv/bin/python scripts/deploy_frontend.py
terraform -chdir=infrastructure output site_url
```

Valider l’identité de l’expéditeur SES et, si le compte est en sandbox SES, celle des destinataires. Confirmer également les souscriptions aux alertes reçues par email. Le site utilise une adresse HTTPS CloudFront, sans domaine personnalisé.

Les secrets, paramètres locaux et états Terraform sont exclus de Git. Conserver l’état et ses sauvegardes pour gérer les ressources existantes. Avec `deletion_protection=false` (valeur par défaut), la suppression de l’infrastructure supprime aussi les données, sans snapshot final RDS. Une alerte budgétaire n’arrête pas les ressources.

## Vérifications

```bash
make check
terraform -chdir=infrastructure init -backend=false -input=false
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure test
```

`make check` nécessite Terraform et les dépendances Python/Node. Les tests Terraform utilisent des fournisseurs simulés.

Pour exécuter aussi les tests de concurrence PostgreSQL :

```bash
docker compose up -d db
TEST_DATABASE_URL='postgresql+psycopg://halloween:local-only-password@127.0.0.1:5432/halloween' make test
```

Sans `TEST_DATABASE_URL`, les tests spécifiques à PostgreSQL sont ignorés.
