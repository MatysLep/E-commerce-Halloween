# Architecture cible d’industrialisation

Proposition étudiée le 28 octobre 2026. Cette cible d’industrialisation n’a pas été déployée ; elle est distincte des essais de la solution hybride. Le schéma représente une cible pour une activité commerciale soutenue et des pics saisonniers. La charge, les objectifs de disponibilité et le budget restent à chiffrer : cette cible est un compromis à valider, pas une preuve de conformité Well-Architected.

## Architecture retenue

- CloudFront distribue le frontend et les images depuis S3 privé avec OAC. Route 53 assure la résolution DNS ; le trafic HTTP ne traverse pas Route 53. WAF protège CloudFront et le User Pool Cognito. Shield Advanced est inclus dans cette cible théorique pour la protection DDoS renforcée de CloudFront.
- L’API est sur un Auto Scaling Group EC2 Graviton, réparti sur deux AZ à Paris. L’ALB interne est une origine VPC CloudFront, disponible dans eu-west-3. Les ressources applicatives et les bases n’ont pas d’IP publique. Les endpoints VPC et les NAT sont dimensionnés par AZ selon les appels réellement nécessaires. Prévoir aussi les prérequis des VPC origins, dont l’Internet Gateway attachée au VPC.
- Aurora PostgreSQL conserve le modèle relationnel du projet : un writer et un reader dans deux AZ, avec stockage Aurora réparti sur trois AZ et réplication Global Database vers l’Irlande. RDS Proxy gère les connexions EC2 et Lambda. Utiliser l’endpoint writer pour les transactions et les lectures qui exigent les dernières écritures ; les lectures tolérant du retard peuvent utiliser un endpoint reader distinct. Les requêtes doivent rester indexées et les connexions plafonnées.
- ElastiCache Valkey sert le catalogue fréquemment consulté avec TTL, invalidation et repli vers Aurora. Le serveur vérifie les prix sur le writer au moment de commander. La perte du cache ne doit pas empêcher une commande.
- Deux publishers EC2 dans un ASG dédié publient l’outbox vers SNS, indépendamment de la charge HTTP. Les événements métier et l’outbox sont écrits dans la même transaction. Des verrous à durée limitée coordonnent les publishers ; un arrêt après publication peut provoquer une répétition. Un reconciliateur détecte les événements et traitements durablement bloqués.
- SNS distribue vers SQS workflow (CommandeCreee), SQS notification (CommandeCreee) et SQS audit (tous les événements). Chaque file possède sa DLQ, son alarme et une procédure de rejeu.
- Une Lambda starter démarre une exécution Step Functions Standard avec un identifiant déterministe et un suivi durable de la commande. Le workflow appelle les Lambdas d’emballage puis d’expédition, avec retries, catch, timeouts et intervention manuelle en cas d’échec persistant. Les transitions métier restent enregistrées dans Aurora, avec déduplication transactionnelle et outbox. Une transition déjà réalisée ne doit pas être répétée lors d’une reprise. Il n’existe pas de garantie générale « exactement une fois » sur les effets externes.
- La confirmation à l’écran suit immédiatement le commit de la commande. L’email passe par Lambda et SES. Le suivi d’envoi réduit les doublons mais ne rend pas atomiques l’appel SES et l’écriture SQL. Les Lambdas utilisant D1 sont attachées au VPC et disposent de la connectivité nécessaire vers leurs autres services.
- L’archivage écrit chaque événement sous une clé S3 déterministe basée sur event_id. Athena lit l’archive avec un catalogue Glue. Ne conserver que les informations personnelles nécessaires et limiter leur présence dans les logs.

D1 est un renvoi de diagramme vers RDS Proxy puis Aurora, pas un autre service ni une autre base. Les blocs sont des regroupements logiques ; la limite réseau des Lambdas est précisée par leur accès D1.

## Industrialisation et exploitation

CodePipeline et CodeBuild exécutent Terraform, les validations, les tests et l’analyse des dépendances. CodeDeploy réalise les déploiements EC2 blue/green et Lambda canary. Les migrations de base doivent être rétrocompatibles pendant la coexistence des versions, et le retour arrière doit être testé. Les changements destructifs demandent une procédure dédiée.

CloudWatch et X-Ray suivent les erreurs, la latence, l’âge des messages SQS, les DLQ et le retard de publication de l’outbox, avec corrélation commande_id / event_id. GuardDuty et Security Hub alimentent le traitement des alertes ; CloudTrail et Config conservent les traces d’audit et les changements de configuration.

Organizations sépare production, préproduction et sécurité/logs. IAM applique les droits minimaux ; Secrets Manager et KMS protègent les secrets et données ; Systems Manager gère les accès administratifs et correctifs. Budgets et Cost Explorer suivent le coût par commande et les ressources inutilisées. Les budgets sont des alertes, pas un plafonnement automatique de la dépense.

## Reprise après sinistre

La production reste en eu-west-3. Le secours proposé en eu-west-1 est une extension explicite du périmètre régional, à faire accepter pour une éventuelle réalisation.

Le choix corrigé est un **warm standby avec fonctionnement dégradé**. Deux environnements régionaux sont déjà déployés : Paris actif, sur deux AZ, et Irlande à capacité réduite, sur deux AZ, avec un ALB et un Auto Scaling Group indépendants. Deux petites EC2 sont maintenues en Irlande pour éviter qu’une instance de secours unique soit un point de panne. Ce nombre et les tailles doivent être validés par les tests de charge. Les services serverless sont prêts mais leurs traitements à effets métier sont désactivés tant que la région est passive.

Aurora Global Database réplique de manière asynchrone les données depuis Paris vers un cluster secondaire en Irlande disposant d’au moins une instance active. La topologie et la taille des instances du secondaire doivent correspondre au service dégradé visé. La haute disponibilité locale de ce cluster demande un reader dans une autre AZ ; une seule instance secondaire reste un compromis de coût. Le schéma ne promet donc pas deux instances Aurora de secours permanentes. Après promotion, les applications rejoignent le RDS Proxy régional approprié. Les sauvegardes isolées, leur copie et Vault Lock sont conservés : la réplication ne remplace pas les sauvegardes.

Chaque Auto Scaling Group adapte ses propres EC2. Paris combine une hausse planifiée avant septembre et un scaling dynamique sur les requêtes par cible ALB ; latence, erreurs et connexions SQL surveillent la capacité utile. Lors de la bascule, la procédure relève le minimum de capacité en Irlande puis laisse le scaling gérer la demande. Les quotas, temps de lancement, capacités maximales et connexions SQL doivent être testés. L’Auto Scaling ne déclenche pas la promotion d’Aurora ni le basculement du trafic.

La procédure de bascule doit être exécutable depuis la région de secours : bloquer les écritures applicatives de l’ancienne région et isoler ses traitements ; promouvoir Aurora en Irlande ; vérifier SQL, identités, secrets, connectivité et API ; modifier le routage CloudFront vers l’origine VPC Irlande pour toutes les méthodes ; réconcilier les commandes et activer les traitements ; réouvrir la prise de commande. La protection contre deux régions actives simultanément et le retour à Paris font partie des exercices. L’isolement de Paris doit rester contrôlé après son retour et avant toute reprise de ses traitements.

Le simple failover d’un groupe d’origines CloudFront ne couvre pas POST : la bascule de l’API est explicite et pilotée par le plan de reprise, avec prise en compte du délai de propagation du routage et du comportement des clients. Le service ne doit pas être présenté comme sans interruption.

SQS et les exécutions Step Functions ne sont pas répliqués automatiquement. La reprise reconstruit les traitements depuis les commandes et événements durables. Un événement marqué publié peut devoir être republié : le rejeu ne doit pas dépendre seulement de l’outbox en attente. Il faut également réconcilier les emails ou expéditions déjà effectués. La réplication asynchrone peut laisser perdre les dernières écritures d’une panne imprévue.

Le mode dégradé privilégie le catalogue, les connexions des comptes existants compatibles et les commandes, ces dernières seulement après validation du nouveau writer. Les emails et la logistique peuvent être retardés, et le reporting est suspendu. Le cache froid est toléré avec limitation de charge pour protéger la base. Les RTO et RPO doivent être fixés et mesurés, ainsi que la capacité minimale réellement assurée pendant le secours.

Cognito propose la réplication multi-région, y compris Paris et Irlande, avec le plan Essentials ou Plus et des clés KMS multi-région. La réplique reste dans le compte applicatif. Le mode secondaire a des limites : pas de création de nouveaux utilisateurs ni de réinitialisation de mot de passe ; la documentation consultée exclut aussi le MFA TOTP dans la réplique. Choisir et tester les facteurs d’authentification compatibles avec le plan de reprise. Les paramètres régionaux, dont SES, les triggers et WAF, demandent une configuration spécifique.

## Justification des six piliers

| Pilier | Mesures et preuves attendues |
|---|---|
| Excellence opérationnelle | Infrastructure reproductible, CI/CD, logs corrélés, SLO, procédures d’incident et exercices de rejeu. |
| Sécurité | Origines privées, Cognito, WAF, Shield Advanced, moindre privilège, chiffrement, comptes séparés et réponse aux alertes. |
| Fiabilité | Répartition sur 2 AZ, capacité suffisante après perte d’une AZ, Aurora avec readers, outbox, idempotence, DLQ et restauration testée. |
| Efficacité des performances | Tests de charge, cache mesuré, autoscaling, concurrence Lambda limitée, pool de connexions et index SQL. |
| Optimisation des coûts | Coût par commande, right-sizing, rétentions adaptées, alertes et engagements seulement après mesure du socle stable. |
| Développement durable | Graviton après validation de compatibilité, cache, compression, scaling et arrêt des environnements de test. |

L’ajout de composants améliore certains objectifs mais augmente le coût et l’exploitation. Aurora Global Database avec des instances dans les deux régions, le cache, les publishers dédiés et Shield Advanced ne seraient pas proportionnés à une petite démonstration. Shield Advanced est un choix de protection premium assumé, à comparer à la perte métier possible : le tarif officiel consulté indique 3 000 USD/mois, avec engagement minimal d’un an et frais supplémentaires possibles. Les hypothèses de trafic, le dimensionnement et le chiffrage saisonnier sont présentés dans [l’estimation détaillée](estimation-industrialisation.md).

MSK n’est pas ajouté à cette nouvelle cible : les besoins définis sont couverts par SNS/SQS, Aurora et l’archive S3. Un besoin concret de streaming, d’intégration Kafka ou de multiples consommateurs avec replay indépendant pourrait justifier une étude séparée.

## Sources techniques et icônes

- [CloudFront VPC origins et régions supportées](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [Aurora : disponibilité et durabilité](https://docs.aws.amazon.com/rds/latest/auroraextendedcontent/aurora-faq-availability-and-durability.html)
- [RDS Proxy : endpoints Aurora](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-proxy-endpoints.html)
- [Outbox transactionnelle](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
- [Step Functions : Standard et Express](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html)
- [Aurora Global Database : bascule et risque de perte de données](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database-disaster-recovery.html)
- [CloudFront : limites du failover d’origine](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/high_availability_origin_failover.html)
- [AWS Backup : fonctions par ressource](https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html)
- [Cognito : réplication multi-région et limites](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-multi-region.html)
- [Shield : FAQ](https://aws.amazon.com/shield/faqs/)
- [Coûts WAF et Shield Advanced](https://aws.amazon.com/blogs/aws-cloud-financial-management/how-to-estimate-your-aws-waf-and-aws-shield-advanced-costs/)
- [AWS Well-Architected Framework](https://wa.aws.amazon.com/index.en.html)
- [Icônes officielles AWS](https://aws.amazon.com/architecture/icons/) — paquet du 31 juillet 2026 ; symboles intégrés aux SVG conservés dans ce dossier.

Le SVG et le PNG de la cible sont conservés dans ce dossier. Leur générateur initial n’est pas inclus dans le dépôt ; le script `scripts/generate_architecture.py` ne régénère que le schéma hybride. Le schéma et ses connexions ont été vérifiés visuellement ; cette vérification ne remplace pas les essais d’une infrastructure déployée.
