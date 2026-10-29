# Les outils de préparation

Ces scripts se lancent depuis la racine avec l’environnement Python du projet.

- `build.py` fabrique `build/release.tar.gz` pour EC2 et `build/lambda.zip` pour Lambda. Il télécharge les dépendances Linux x86_64 et les certificats publics RDS. Il fonctionne aussi sur un Mac ARM : les bibliothèques de votre Mac ne sont pas copiées dans Lambda.
- `deploy_frontend.py` lit les sorties Terraform, téléverse la boutique dans S3 et demande à CloudFront d’actualiser son cache. Il remplace uniquement la configuration publique, sans secret.

La publication utilise le profil `aws_profile` des sorties Terraform et compare l’identité STS au champ `aws_account_id`. Elle s’arrête avant les uploads si le compte ne correspond pas. Cela évite une erreur lorsque le profil par défaut du terminal appartient à un ancien compte.
- `check_docs.py` vérifie qu’un `readme.md` existe dans chaque dossier source suivi ou non ignoré par Git.
- `generate_architecture.py` génère le schéma vectoriel de l’architecture hybride avec les logos officiels AWS. Il lit le mode haute disponibilité et le montant du budget dans `infrastructure/terraform.tfvars` s’il existe. La topologie est dessinée explicitement à partir du Terraform ; ce script ne découvre pas automatiquement de nouveaux services ajoutés au code.
- `render_architecture.mjs` transforme ce SVG en PNG avec Sharp pour l’insérer dans le rapport ou la présentation.

```bash
make build
.venv/bin/python scripts/check_docs.py
# Uniquement après le déploiement AWS :
.venv/bin/python scripts/deploy_frontend.py
# Régénérer le schéma et son image après installation des outils Node :
npm ci
npm run diagram
```

`build/` est généré et ignoré par Git. Il contient les dépendances et les archives, pas une nouvelle partie du code à maintenir. Il faut reconstruire les archives après chaque changement Python, puis examiner le nouveau plan Terraform.
