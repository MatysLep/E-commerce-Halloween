# L’infrastructure : les plans de construction AWS

Terraform décrit les services à créer. `plan` propose les changements, `apply` les exécute. Le guide complet est dans [`doc/deploiement.md`](../doc/deploiement.md).

`sender_email` choisit l’expéditeur des confirmations de commande. `alarm_emails` accepte de une à dix adresses distinctes : chacune reçoit une souscription aux alertes et figure parmi les destinataires des alertes de budget. Les adresses réelles de l’équipe se renseignent dans `terraform.tfvars`, ignoré par Git.

| Fichier | Ressources concernées |
| --- | --- |
| `versions.tf` | Les fournisseurs, la région Paris et les valeurs partagées. |
| `variables.tf` | Les paramètres que vous choisissez. |
| `network.tf` | Le réseau, deux zones, les sorties NAT et les règles de connexion. |
| `database.tf` | PostgreSQL RDS, sauvegardes, TLS et secret du compte applicatif. |
| `compute.tf` | EC2, ALB privé et adaptation du nombre d’instances. |
| `bootstrap.sh.tftpl` | L’installation et le démarrage automatique des services EC2. |
| `migrations.tf` | La Lambda d’administration qui prépare la base. |
| `messaging.tf` | SNS, SQS, files d’erreurs, Lambdas métier et identité SES. |
| `frontend.tf` | CloudFront, origine VPC vers l’ALB, accès privé S3, connexion Cognito et WAF. |
| `storage.tf` | Les fichiers du site, les archives applicatives et l’audit CloudTrail. |
| `iam.tf` | Les permissions des serveurs et des Lambdas. |
| `monitoring.tf` | Les alarmes et l’alerte de budget. |
| `outputs.tf` | Les informations utiles après le déploiement. |
| `architecture.tftest.hcl` | Les vérifications de configuration avec un AWS simulé. |
| `.terraform.lock.hcl` | Les versions et empreintes des fournisseurs retenus. |

Le choix `high_availability=false` lance une EC2, un NAT et un RDS sans standby. Il reste payant et n’assure pas la haute disponibilité. Avec `true`, le minimum passe à deux EC2, deux NAT et RDS Multi-AZ. L’ALB utilise deux zones dans les deux modes.

Le site utilise une adresse fournie par AWS, comme `https://d123example.cloudfront.net`, avec le certificat HTTPS par défaut de CloudFront. Aucun domaine personnalisé, aucune zone Route 53 et aucun certificat ACM à valider ne sont requis.

Les EC2 et les bases n’ont pas d’IP publique. L’ALB est interne, dans les deux sous-réseaux privés. CloudFront le rejoint via une origine VPC : les flux CloudFront → ALB et ALB → EC2 utilisent HTTP dans le réseau privé. Le groupe de sécurité de l’ALB autorise le port 80 depuis la prefix list CloudFront et le listener exige un en-tête secret. Le trafic navigateur → CloudFront reste en HTTPS et le trafic SQL utilise TLS avec vérification du certificat. Systems Manager remplace SSH.

L’Internet Gateway reste attachée au VPC, car c’est un prérequis des origines VPC CloudFront. Elle n’est pas utilisée pour acheminer le flux CloudFront → ALB privé. L’endpoint Gateway S3 est conservé ; les autres sorties applicatives utilisent toujours les NAT.

Le compte SQL utilisé au quotidien n’a pas de droits de création ou de suppression de tables. Seule la Lambda de migration reçoit le secret administrateur. Les instances peuvent lui demander d’appliquer la version livrée, sans lui transmettre de commande SQL.

`terraform.tfvars`, les plans et l’état peuvent contenir des informations sensibles. Ils sont ignorés par Git. En équipe, utilisez un backend d’état S3 privé, chiffré, versionné, avec verrouillage et accès limité. Le mot de passe applicatif généré est présent dans l’état Terraform : Secrets Manager ne supprime pas cette contrainte.
