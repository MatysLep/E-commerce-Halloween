# Déployer sur AWS, étape par étape

## Ce qui est livré

Terraform prépare l’architecture hybride à Paris : réseau privé, RDS, EC2 et services systemd, ALB privé relié à une origine VPC CloudFront, S3 privé, Cognito, SNS/SQS, trois Lambdas métier, une Lambda de migration, SES, WAF, CloudTrail, alarmes et budget. Le navigateur accède au site en HTTPS à l’adresse fournie par CloudFront.

La Lambda de migration est appelée par les EC2 au démarrage. Elle applique les migrations, insère uniquement les produits manquants et prépare un compte SQL applicatif limité. L’API et le publisher ne démarrent qu’après son succès.

La construction locale, les tests et les validations Terraform ne nécessitent pas de compte AWS. Le déploiement réel nécessite vos paramètres, permissions et confirmations de services.

## Coûts et prérequis

Cette architecture **ne garantit pas le Free Tier**. ALB, NAT, RDS, WAF, stockage, secrets et trafic peuvent être facturés. Pour un exercice à zéro coût AWS, utiliser la version Docker locale et présenter le plan cloud. Le PDF autorise la présentation d’une architecture dépassant le budget sans la déployer.

Le profil RDS réduit (`high_availability=false`, valeur par défaut) est dimensionné à `db.t4g.micro`, Single-AZ, 20 Gio de SSD `gp2`, sans extension automatique du stockage. Il conserve un jour de sauvegardes automatiques et n’exporte pas les logs PostgreSQL vers CloudWatch. Le chiffrement, le réseau privé, Secrets Manager et le snapshot final restent activés. Le profil HA est payant et conserve son dimensionnement plus important.

L’offre RDS actuelle repose sur les crédits des plans Free/Paid. L’ancienne offre, pour les inscriptions antérieures au 15 juillet 2025, était limitée à douze mois : son quota de 750 heures et 20 Go `gp2` ne constitue pas une promesse de gratuité pour un déploiement en octobre 2026. Vérifier le solde, l’expiration des crédits et les services autorisés dans votre compte de formation. [Conditions AWS RDS Free Tier](https://aws.amazon.com/rds/free/), [FAQ RDS](https://aws.amazon.com/rds/faqs/).

Secrets Manager reste facturé séparément selon l’offre du compte. Réduire la rétention ne garantit pas un stockage de sauvegardes gratuit, et les snapshots conservés après suppression peuvent continuer à coûter. Si RDS est déjà déployé, examiner le plan avant application : un volume qui a grandi ne peut pas être réduit directement à 20 Gio. [Gestion des secrets RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html), [stockage autoscaling RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PIOPS.Autoscaling.html).

Préparer :

- Un compte AWS de formation autorisant les services de ce projet, et une session AWS CLI valide, de préférence avec IAM Identity Center.
- Des permissions de déploiement permettant de créer une origine VPC CloudFront et, si nécessaire, son rôle lié au service dans le compte. Les comptes de formation peuvent limiter ces permissions.
- Une adresse email d’envoi SES dont vous contrôlez la boîte (`sender_email`), et les adresses de réception des alertes (`alarm_emails`).
- Les quotas EC2, RDS, NAT/EIP, VPC et Lambda. Les réservations Lambda totalisent **7 exécutions** ; AWS impose aussi une réserve de concurrence non réservée. Un compte avec un faible quota Lambda peut nécessiter une hausse de quota.
- Python 3.12+, Terraform 1.10+, AWS CLI v2 et les dépendances du projet.

La boutique utilise l’URL HTTPS attribuée par CloudFront, comme `https://d123example.cloudfront.net`. Vous n’avez aucun domaine à acheter ni zone Route 53 à créer. Terraform utilise le certificat par défaut CloudFront et configure aussi cette URL pour les retours de connexion Cognito. WAF global est administré via `us-east-1` ; les données métier et les fonctions restent à Paris.

L’ALB reste interne au VPC. CloudFront le rejoint par une origine VPC en HTTP privé, puis l’ALB contacte les EC2 en HTTP privé. Le navigateur utilise HTTPS et la connexion SQL utilise TLS. L’Internet Gateway attachée au VPC satisfait le prérequis CloudFront ; ce flux privé ne traverse pas le NAT.

## Préparer une version

À la racine :

```bash
make install
npm ci
make check
make build
# Seulement si terraform.tfvars n’existe pas déjà :
test -f infrastructure/terraform.tfvars || cp infrastructure/terraform.tfvars.example infrastructure/terraform.tfvars
```

Renseigner vos valeurs dans `terraform.tfvars` en conservant les adresses de l’équipe déjà saisies. Les anciennes variables `hosted_zone_id` et `api_domain` ont été retirées de cette version. Garder `high_availability=false` pour la version réduite et `deletion_protection=true` tant que des données doivent être conservées. `enable_waf=false` réduit le périmètre et certains frais, mais retire WAF de la solution déployée.

Le script de construction prépare des bibliothèques Linux x86_64, même sur Mac ARM. Les archives contiennent les migrations et le certificat RDS. Elles doivent être reconstruites après tout changement Python. Aucun paquet ne doit être téléchargé par une Lambda au démarrage.

## Valider, examiner, appliquer

```bash
terraform -chdir=infrastructure init
terraform -chdir=infrastructure validate
terraform -chdir=infrastructure test
terraform -chdir=infrastructure plan -out=deployment.tfplan
```

Les tests Terraform utilisent des services simulés ; ils ne créent rien sur AWS. Le vrai `plan` interroge votre compte et montre les ressources prévues. Examiner la région, le nombre d’instances, les remplacements, les suppressions et les frais avant d’exécuter :

```bash
terraform -chdir=infrastructure apply deployment.tfplan
.venv/bin/python scripts/deploy_frontend.py
terraform -chdir=infrastructure output site_url
```

L’état local est acceptable pour une démonstration individuelle, mais contient des secrets. Pour travailler à plusieurs, configurer avant le déploiement un backend S3 privé avec chiffrement, versioning et verrouillage `use_lockfile=true`. Ne pas partager l’état par Git ou messagerie. Ne pas lancer deux `apply` en parallèle.

## Terminer la configuration des emails

Ouvrir l’email de validation envoyé par SES à l’expéditeur et confirmer l’identité. Chaque destinataire défini dans `alarm_emails` doit également confirmer sa propre souscription SNS aux alertes. Les alertes de budget sont configurées pour ces mêmes destinataires.

Dans le sandbox SES, les destinataires doivent également être validés auprès de SES. Une adresse vérifiée dans Cognito n’est pas automatiquement vérifiée dans SES. Pour la démo, valider explicitement l’adresse du client de test dans SES ; pour un vrai service, demander la sortie du sandbox dans la région Paris.

Les emails de validation d’inscription Cognito sont distincts des confirmations de commande SES. Si un compte de formation limite les services email, la commande peut fonctionner tandis que la notification attend dans SQS ou la DLQ.

## Vérifications dans le compte déployé

1. Vérifier que les cibles de l’ALB sont saines et que les services EC2 sont actifs dans Systems Manager.
2. Ouvrir l’URL CloudFront et vérifier `/api/health`.
3. Créer un compte via Cognito, confirmer l’email et se connecter.
4. Commander un produit et suivre la progression jusqu’à l’expédition simulée.
5. Vérifier l’email, les logs et l’absence de messages en DLQ.
6. Vérifier qu’un deuxième compte ne voit pas la première commande.
7. Tester une nouvelle tentative avec la même clé et une rupture de stock.
8. Vérifier les alarmes et tester une restauration dans une base séparée avant toute démonstration de résilience.

Ces vérifications réelles restent nécessaires : `terraform validate` vérifie la structure, pas les quotas, la livraison SES ou la disponibilité des services dans votre compte.

## Publier une mise à jour

```bash
make check
make build
terraform -chdir=infrastructure plan -out=deployment.tfplan
terraform -chdir=infrastructure apply deployment.tfplan
.venv/bin/python scripts/deploy_frontend.py
```

Les archives ont des clés S3 basées sur leur empreinte. Une modification du template EC2 déclenche un remplacement progressif des instances. Les Lambdas sont mises à jour directement : ce projet ne réalise pas de déploiement canary. Les migrations doivent donc rester compatibles avec les versions qui coexistent. Les nouvelles Lambdas peuvent être disponibles avant la fin des migrations : une évolution doit tolérer la structure précédente ou être livrée en plusieurs étapes.

Le premier déploiement attend RDS, l’origine VPC CloudFront, la distribution et les instances. Le temps dépend du compte et de la région ; ne pas interrompre un `apply` simplement parce qu’il est long.

## Références utilisées

- [Vérification des jetons Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-access-token.html)
- [Origines VPC CloudFront : prérequis et régions prises en charge](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [Réponses partielles SQS/Lambda](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html)
- [Délai de visibilité et reprise SQS](https://aws.amazon.com/blogs/compute/understanding-how-aws-lambda-scales-when-subscribed-to-amazon-sqs-queues/)

Les choix de coût et les quotas doivent être vérifiés au moment du déploiement ; ce guide ne promet pas un tarif ni une gratuité.
