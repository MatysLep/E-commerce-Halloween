# L’infrastructure : les plans de construction AWS

Terraform décrit les services à créer. `plan` propose les changements, `apply` les exécute. Le guide complet est dans [`doc/deploiement.md`](../doc/deploiement.md).

`aws_profile` sélectionne explicitement un profil AWS CLI pour les deux fournisseurs (Paris et WAF global). `expected_account_id` permet de limiter ces fournisseurs à un seul compte : un profil connecté à un autre compte est refusé avant le déploiement. Renseigner ces deux valeurs dans `terraform.tfvars` pour éviter de mélanger les ressources de comptes différents. Le script de publication du frontend réutilise le profil enregistré dans les sorties Terraform et vérifie le compte avant tout envoi.

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
| `teardown.tftest.hcl` | Les vérifications du nettoyage complet et du mode protégé. |
| `notifications.tftest.hcl` | Le routage des confirmations et expéditions vers la file de notification. |
| `lambda_concurrency.tftest.hcl` | Les vérifications des limites Lambda pour les petits comptes et des réservations optionnelles. |
| `.terraform.lock.hcl` | Les versions et empreintes des fournisseurs retenus. |

Le choix `high_availability=false` lance une EC2, un NAT et un RDS sans standby. Il reste payant et n’assure pas la haute disponibilité. Avec `true`, le minimum passe à deux EC2, deux NAT et RDS Multi-AZ. L’ALB utilise deux zones dans les deux modes.

Pour RDS, le mode réduit utilise `db.t4g.micro`, 20 Gio de SSD `gp2`, aucune extension automatique du stockage, une rétention des sauvegardes d’un jour et aucun export des logs PostgreSQL vers CloudWatch. Le mode HA conserve `db.t4g.small`, `gp3`, une limite d’extension à 50 Gio et sept jours de sauvegardes. Dans les deux cas, RDS reste privé et chiffré, avec des secrets gérés. Un snapshot final est conservé uniquement si `deletion_protection=true`. Secrets Manager et les snapshots conservés peuvent être facturés séparément.

Ces réglages réduisent la consommation et reprennent le dimensionnement de l’ancienne offre RDS gratuite. Ils ne garantissent pas la gratuité du compte : l’offre actuelle RDS utilise des crédits et l’éligibilité doit être vérifiée dans la facturation AWS. Voir [AWS RDS Free Tier](https://aws.amazon.com/rds/free/).

Le site utilise une adresse fournie par AWS, comme `https://d123example.cloudfront.net`, avec le certificat HTTPS par défaut de CloudFront. Aucun domaine personnalisé, aucune zone Route 53 et aucun certificat ACM à valider ne sont requis.

Les EC2 et les bases n’ont pas d’IP publique. L’ALB est interne, dans les deux sous-réseaux privés. CloudFront le rejoint via une origine VPC : les flux CloudFront → ALB et ALB → EC2 utilisent HTTP dans le réseau privé. Le groupe de sécurité de l’ALB autorise le port 80 depuis la prefix list CloudFront et le listener exige un en-tête secret. Le trafic navigateur → CloudFront reste en HTTPS et le trafic SQL utilise TLS avec vérification du certificat. Systems Manager remplace SSH.

L’Internet Gateway reste attachée au VPC, car c’est un prérequis des origines VPC CloudFront. Elle n’est pas utilisée pour acheminer le flux CloudFront → ALB privé. L’endpoint Gateway S3 est conservé ; les autres sorties applicatives utilisent toujours les NAT.

Le compte SQL utilisé au quotidien n’a pas de droits de création ou de suppression de tables. Seule la Lambda de migration reçoit le secret administrateur. Les instances peuvent lui demander d’appliquer la version livrée, sans lui transmettre de commande SQL.

`terraform.tfvars`, les plans et l’état peuvent contenir des informations sensibles. Ils sont ignorés par Git. En équipe, utilisez un backend d’état S3 privé, chiffré, versionné, avec verrouillage et accès limité. Le mot de passe applicatif généré est présent dans l’état Terraform : Secrets Manager ne supprime pas cette contrainte.

Les quatre Lambdas attendent 30 secondes après la création ou la modification de leurs politiques IAM avant de configurer leur accès au VPC. Le fournisseur Terraform `time` gère cette attente, qui est rejouée quand l’identifiant ou le contenu d’une politique change. Ce délai atténue la propagation IAM ; il ne remplace pas les permissions réseau requises et n’impose pas de nouvelle attente à chaque plan inchangé.

En cas de plantage Terraform, conserver l’état et sa sauvegarde : AWS peut avoir terminé certaines créations. La [procédure de reprise](../doc/exploitation.md#si-terraform-plante-pendant-lenregistrement-de-létat) explique comment vérifier les ressources et reconstruire un plan sans repartir de zéro.

`enable_lambda_reserved_concurrency=false` évite les réservations incompatibles avec les comptes limités à dix exécutions Lambda. Chaque déclencheur SQS conserve sa limite de deux exécutions simultanées ; les fonctions partagent la capacité disponible du compte. La migration est protégée par un verrou transactionnel PostgreSQL, même si plusieurs EC2 la demandent en même temps. Avec un quota suffisant, `true` réserve deux exécutions par consommateur et une pour la migration.

Le profil de démonstration utilise `deletion_protection=false` par défaut : `terraform destroy` peut vider les trois buckets S3 (versions comprises), supprimer RDS sans snapshot final et avec ses sauvegardes automatiques, supprimer le secret applicatif sans fenêtre de récupération, ainsi que l’ALB et Cognito sans protection bloquante. Les données, comptes clients et journaux d’audit sont alors perdus. CloudFront est supprimé après sa désactivation ; cette étape et le nettoyage des interfaces réseau Lambda peuvent prendre plusieurs minutes.

Pour un déploiement existant, appliquer d’abord ces paramètres avec `terraform apply`, puis lancer `terraform destroy` : changer seulement les fichiers avant un destroy ne met pas à jour les valeurs enregistrées dans l’état. `deletion_protection=true` réactive les protections, refuse la suppression des buckets non vides et conserve un snapshot final RDS et une fenêtre de récupération du secret de sept jours. Voir la [procédure de suppression](../doc/exploitation.md#arrêter-les-frais-de-démonstration-aws).
