# Minuit — E-commerce Halloween

Projet pédagogique réalisé à **IMT Nord Europe**, dans le module **Infrastructures cloud et virtualisation — FISA TI 2027**. Minuit propose un catalogue Halloween, un panier, des comptes clients et le suivi des commandes jusqu’à une expédition simulée. Aucun paiement ni envoi physique n’est effectué.

**Équipe :** Bahir Boudouma Lambarki, Tarik Fellahi et Matys Lepretre.

**Accès rapide :** [Installation](#installation) · [Architectures](#réflexion-et-présentation-des-architectures) · [Tests](#vérifier-le-projet) · [Rapport académique](doc/rapport-academique.docx) · [Documentation](doc/README.md)

## Contexte

Le [sujet du projet](doc/AWS%20Project%20FISA%202026.pdf) demande une boutique évolutive, résiliente et maîtrisée en coût, utilisant EC2, des services serverless, SNS et Terraform. Une commande doit être enregistrée pour l’audit, confirmée au client, puis traitée en arrière-plan. Halloween introduit une question de dimensionnement : comment absorber un pic saisonnier sans conserver toute l’année une capacité inutile ?

Notre réalisation associe une API sur machines virtuelles à des traitements événementiels serverless. Le dépôt présente également une cible d’industrialisation plus ambitieuse. La démonstration locale fonctionne sans compte AWS ; les essais cloud historiques sont documentés séparément de l’état actuel du service.

![Aperçu de la démonstration locale](doc/demonstration-locale.png)

## Réflexion et présentation des architectures

### Machines virtuelles ou serverless

Nous avons comparé deux modes d’exécution avant de retenir une combinaison des deux :

| Critère | API sur machines virtuelles | Variante entièrement serverless étudiée |
| --- | --- | --- |
| Entrée HTTP | ALB et API FastAPI sur EC2 | API Gateway et Lambda |
| Exploitation | Services persistants, système et capacité à gérer | Exécution à la demande, limites de durée et de concurrence à gérer |
| Données | PostgreSQL et transactions relationnelles | DynamoDB à étudier, ou SQL avec maîtrise des connexions |
| Charge saisonnière | Capacité minimale permanente et Auto Scaling | Capacité adaptée aux invocations, sous réserve des quotas |
| Coût | Socle permanent, même à faible trafic | Dépend de l’usage et des services associés ; gratuité non garantie |
| Travail requis | Implémenté dans la solution hybride | Adaptation de l’API et éventuellement du modèle de données ; non implémentée |

Nous retenons EC2 pour conserver une API Python persistante et un modèle transactionnel lisible, puis Lambda pour isoler l’emballage, l’expédition simulée et les notifications. SNS distribue les événements et SQS absorbe les décalages de vitesse des consommateurs. MSK n’est pas retenu : aucun besoin de streaming Kafka ne justifie ici son coût et sa complexité.

**Périmètre pédagogique :** le sujet demande deux solutions, l’une sur machines virtuelles et l’autre serverless. La comparaison ci-dessus expose ces alternatives ; le dépôt contient une seule implémentation Terraform hybride. La cible industrialisée ci-dessous reste elle aussi hybride et ne doit pas être présentée comme une seconde implémentation entièrement serverless.

### Architecture 1 — Solution hybride réalisée

![Architecture hybride AWS](doc/architecture/architecture-aws-hybride.png)

CloudFront distribue le frontend depuis S3 privé et transmet les appels API à un ALB interne par une origine VPC. L’ALB dessert l’API FastAPI sur EC2. Cognito gère l’identité ; RDS PostgreSQL conserve produits, commandes, événements et reçus de traitement. Un publisher sur EC2 transmet l’outbox à SNS, qui alimente les files SQS des Lambdas métier. SES envoie les emails de confirmation et d’expédition.

Le mode réduit conserve une EC2 désirée, un NAT et RDS Single-AZ. `high_availability=true` augmente la capacité EC2 et prévoit un NAT par zone, **mais RDS reste Single-AZ dans le code actuel**. La disponibilité complète de la plateforme n’est donc pas démontrée par cette option. Le navigateur utilise HTTPS ; les flux privés CloudFront → ALB → EC2 utilisent HTTP et les connexions SQL vérifient TLS.

### Architecture 2 — Cible d’industrialisation proposée

![Architecture cible d’industrialisation](doc/architecture/architecture-aws-industrialisation.png)

Cette cible ajoute Aurora PostgreSQL et RDS Proxy, un cache Valkey, des publishers dédiés, Step Functions pour orchestrer les traitements, une archive S3 exploitable avec Glue/Athena et une chaîne de livraison plus complète. Un environnement de secours à capacité réduite en Irlande complète la production à Paris.

Le secours prévu est un **warm standby** : des ressources sont déjà présentes, mais leur activation exige une procédure de bascule et de réconciliation des traitements. Les objectifs de reprise (RTO/RPO), la capacité et le retour à la région principale restent à mesurer. Cette architecture est **une proposition non déployée**, détaillée dans [l’étude d’industrialisation](doc/architecture/industrialisation.md).

### Comparaison et budget

| Dimension | Hybride réalisée | Industrialisation proposée |
| --- | --- | --- |
| Finalité | Démonstration reproductible et apprentissage | Exploitation commerciale avec exigences renforcées |
| Base | RDS PostgreSQL Single-AZ | Aurora, Proxy et réplication vers le secours |
| Traitements | SNS, SQS, Lambdas | Orchestration Step Functions et réconciliation |
| Disponibilité | Limites assumées du mode réduit | Multi-AZ et reprise multi-région à valider |
| Exploitation | GitHub Actions, Terraform, CloudWatch | Déploiements progressifs, gouvernance et supervision renforcées |
| Estimation conservée | 98,45 USD/mois | 4 652,46 USD hors saison ; 5 039,38 USD en pointe |

Les [estimations hybride](doc/architecture/estimation-hybride.md) et [industrialisée](doc/architecture/estimation-industrialisation.md), établies les 29–30 octobre 2026, reposent sur des hypothèses différentes de trafic et de disponibilité. Ce ne sont ni des factures ni des devis actualisés. Le scénario industrialisé prévoit onze mois faibles et un mois de pointe, soit **56 216,44 USD/an**. Son socle permanent et Shield Advanced expliquent une part importante du coût.

La solution AWS réduite n’est pas à coût nul : NAT, ALB et RDS restent actifs. L’alerte budgétaire n’arrête pas la facturation. Pour une démonstration sans consommation AWS, utiliser Docker local. Une adaptation cloud réellement compatible avec les crédits et contraintes du compte doit être étudiée séparément.

## Stack technique

| Couche | Technologies et rôle |
| --- | --- |
| Interface | HTML, CSS, JavaScript natifs ; catalogue, comptes et commandes |
| API et métier | Python 3.12+, FastAPI, Uvicorn, SQLAlchemy |
| Données | PostgreSQL 16, Alembic ; SQLite pour le développement léger |
| Cloud | EC2, Lambda, S3, CloudFront, ALB, RDS, Cognito, SNS, SQS, SES |
| Sécurité et exploitation | IAM, Secrets Manager, WAF optionnel, CloudWatch, CloudTrail |
| Infrastructure | Terraform 1.10+ ; versions des fournisseurs dans `.terraform.lock.hcl` |
| Qualité | pytest, tests Node.js, Ruff, Prettier, GitHub Actions |
| Environnement local | Docker Compose, Make ; Node.js 24 pour les outils frontend |

Les versions Python sont fixées dans `requirements.txt` et `requirements-dev.txt`, les dépendances Node dans `package-lock.json`.

## Organisation du dépôt

| Dossier | Rôle |
| --- | --- |
| [backend](backend/README.md) | API, règles métier, notifications et migrations SQL |
| [frontend](frontend/README.md) | Pages, scripts, styles et images du catalogue |
| [infrastructure](infrastructure/README.md) | Ressources AWS et tests Terraform simulés |
| [tests](tests/README.md) | Tests de comportement, transactions et sécurité applicative |
| [scripts](scripts/README.md) | Construction, publication, schémas et contrôle documentaire |
| [doc](doc/README.md) | Sujet, rapport, architectures, coûts et preuves de tests |
| [.github](.github/README.md) | Workflow de validation continue |

Chaque dossier source possède un `README.md`. Les dépendances, caches, archives de construction et états Terraform sont générés localement et exclus de Git. Les bases locales, secrets et paramètres propres au compte ne doivent pas être publiés.

## Installation

### Démonstration avec Docker

Prérequis : Git, Docker avec Compose, moteur Docker démarré et ports 8000/5432 disponibles. Après avoir cloné ce dépôt, ouvrir un terminal à sa racine :

```bash
docker compose up --build -d
```

Ouvrir **http://localhost:8000**. Choisir **Compte démo** ou créer un compte local, ajouter un produit, confirmer le panier et consulter l’historique. La commande passe de confirmée à emballée, puis expédiée. Le worker simule les deux emails dans ses logs.

```bash
docker compose logs -f worker
docker compose down
```

L’arrêt conserve le volume PostgreSQL. Le compte démo est partagé et réservé au mode local ; le mode AWS utilise Cognito. La documentation interactive se trouve à **http://localhost:8000/api/docs**.

### Développement sans Docker

Prérequis : Python 3.12+ et Make. Node.js 24 et Terraform 1.10+ sont nécessaires pour tous les contrôles.

```bash
make install
npm ci
make init
make serve
```

Dans un second terminal à la racine :

```bash
make worker
```

Ce mode utilise SQLite dans `halloween.db`. Le fichier `.env.example` décrit des variables utiles, mais l’application ne charge pas automatiquement `.env` : exporter les variables dans le terminal. Pour les transactions concurrentes, utiliser PostgreSQL comme décrit dans [le guide de développement](doc/developpement.md).

### Déploiement AWS

Le [guide de déploiement](doc/deploiement.md) décrit les permissions, la sélection du compte, SES, les quotas et les frais. Après installation des outils :

```bash
make check
make build
test -f infrastructure/terraform.tfvars || cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
# Renseigner le profil, le compte, les emails et les options dans terraform.tfvars.
terraform -chdir=infrastructure init
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure test
terraform -chdir=infrastructure plan -out=deployment.tfplan
```

Examiner le plan et le coût avant de l’appliquer :

```bash
terraform -chdir=infrastructure apply deployment.tfplan
.venv/bin/python scripts/deploy_frontend.py
terraform -chdir=infrastructure output site_url
```

Aucun domaine personnalisé n’est nécessaire. La validation SES de l’expéditeur et, en sandbox, des destinataires reste nécessaire. Consulter [le guide d’exploitation](doc/exploitation.md) pour les reprises, sauvegardes et suppressions de ressources.

## Vérifier le projet

```bash
make check
terraform -chdir=infrastructure init -backend=false -input=false
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure test
```

Pour inclure PostgreSQL et les tests de concurrence :

```bash
docker compose up -d db
TEST_DATABASE_URL='postgresql+psycopg://halloween:local-only-password@127.0.0.1:5432/halloween' make test
```

Les tests SQL utilisent des schémas temporaires isolés. Sans `TEST_DATABASE_URL`, les cas PostgreSQL sont ignorés. Les tests Terraform utilisent des fournisseurs simulés ; ils ne valident ni les quotas ni les permissions d’un compte réel.

Les [contrôles récents](doc/validation-depot.md), l’[historique local](doc/verifications.md) et les [essais AWS du 29 octobre](doc/rapport-tests-api.md) indiquent les périmètres et limites de chaque validation. Les essais historiques ne garantissent pas que le site soit encore en ligne.

## Challenges et apprentissages

- **Fiabiliser la commande.** L’API recalcule les prix en centimes, vérifie le stock et enregistre commande, lignes, événement et outbox dans une transaction. Une clé d’idempotence empêche une nouvelle tentative réseau de créer une deuxième commande.
- **Accepter les répétitions de messages.** SNS/SQS et les reprises imposent des consommateurs idempotents. Les reçus SQL dédupliquent les transitions métier ; l’envoi SES et l’écriture SQL ne sont pas atomiques, donc un doublon d’email reste possible après une panne au mauvais moment.
- **Séparer sécurité et interface.** L’identité et l’accès aux commandes sont contrôlés dans l’API. Les secrets restent côté serveur ; les migrations disposent de droits distincts de ceux de l’application.
- **Passer du local au cloud.** SQLite facilite le démarrage, PostgreSQL valide les verrous, et les essais AWS révèlent les contraintes IAM, SES et réseau. Le blocage SES documenté a nécessité la vérification du destinataire et une correction des permissions.
- **Raisonner sur le coût global.** Des traitements Lambda peu coûteux ne rendent pas gratuits le réseau et la base. Le secours permanent et les protections premium doivent être justifiés par un besoin métier mesurable.
- **Distinguer conception et preuve.** Un schéma multi-région ne démontre pas la résilience. Tests de charge, restauration, bascule et objectifs RTO/RPO constituent les prochaines étapes avant une exploitation réelle.

Le [rapport académique](doc/rapport-academique.docx) développe ces choix, leurs limites et les perspectives d’amélioration.
