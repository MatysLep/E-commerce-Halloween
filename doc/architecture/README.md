# Les schémas d’architecture

L’architecture hybride est celle implémentée dans ce dépôt : une API sur EC2, PostgreSQL RDS et des traitements Lambda déclenchés par SNS/SQS.

- `architecture-aws-hybride.png` : le schéma à jour du Terraform, facile à consulter et à intégrer dans une présentation.
- `architecture-aws-hybride.svg` : sa version vectorielle, qui reste nette en zoomant.
- `architecture-aws-industrialisation.png` et `.svg` : une cible plus ambitieuse pour une activité commerciale importante.
- `industrialisation.md` : les choix, limites et sources de cette cible future.
- `aws-service-symbols.svg` : les logos officiels AWS embarqués localement pour rendre le schéma reproductible, sans chargement d’images externes.
- [Estimation AWS Pricing Calculator de l’architecture hybride](estimation-hybride.md) : lien public, hypothèses de charge et limites du chiffrage du mode réduit.
- [Estimation saisonnière de la cible industrialisée](estimation-industrialisation.md) : mois faible, pointe Halloween, budget pondéré et hypothèses de production/secours.

La cible d’industrialisation ajoute notamment Aurora, cache et secours multi-région. Ces services ne sont pas déployés par le Terraform hybride.

Le schéma hybride représente la configuration Terraform actuelle, sans domaine personnalisé : CloudFront fournit l’adresse HTTPS et rejoint un ALB interne dans les sous-réseaux privés via une origine VPC. Le flux privé CloudFront → ALB utilise HTTP. La configuration affichée est le mode réduit avec une EC2 désirée, un maximum de deux EC2, RDS Single-AZ et un NAT. L’option `high_availability=true` augmente uniquement la capacité EC2 (minimum/désiré 2, maximum 4) et crée un NAT par AZ : le code actuel conserve RDS Single-AZ, `db.t4g.micro`, 20 Gio gp2 et un jour de sauvegardes. Cette option n’assure donc pas la haute disponibilité de la base.

La file de notification reçoit `CommandeCreee` et `ExpeditionTerminee`, pour les emails de confirmation et d’expédition via SES. Chaque mapping SQS limite la concurrence à deux ; la concurrence réservée des Lambdas est désactivée par défaut. Si `enable_lambda_reserved_concurrency=true`, elle passe à deux par fonction métier et à une pour la migration. Sans cette option, la migration n’a pas de limite de concurrence propre à la fonction. Cognito permet la connexion par mot de passe et le flux OAuth avec PKCE.

La Lambda d’administration pour les migrations SQL est représentée dans une section distincte. Elle prépare les tables au démarrage et ne participe pas au traitement des commandes. Le publisher partage les EC2 de l’API, dans un service séparé. Les renvois `D1` pointent tous vers le même RDS ; les sections regroupent les flux et ne définissent pas des réseaux supplémentaires. Les détails de la configuration actuelle se trouvent dans le [README infrastructure](../../infrastructure/README.md).

Pour régénérer le SVG et le PNG depuis la racine : `npm ci`, puis `npm run diagram` (avec l’environnement Python du projet installé). Le script lit `high_availability`, `monthly_budget_usd`, `enable_waf` et `enable_lambda_reserved_concurrency` dans le fichier local de configuration ; toute modification de topologie demande aussi une mise à jour explicite du script de dessin. Les destinataires des alertes restent désignés sans exposer leurs adresses. Le schéma représente le code présent au 29 octobre 2026, sans attester du déploiement AWS.

Les logos proviennent du [paquet officiel d’icônes d’architecture AWS](https://aws.amazon.com/architecture/icons/), édition du 31 juillet 2026. Les tracés originaux sont conservés dans le catalogue SVG ; seuls leur taille et leur placement changent dans le schéma.
