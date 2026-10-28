# Les schémas d’architecture

L’architecture hybride est celle implémentée dans ce dépôt : une API sur EC2, PostgreSQL RDS et des traitements Lambda déclenchés par SNS/SQS.

- `architecture-aws-hybride.png` : le schéma à jour du Terraform, facile à consulter et à intégrer dans une présentation.
- `architecture-aws-hybride.svg` : sa version vectorielle, qui reste nette en zoomant.
- `architecture-aws-industrialisation.png` et `.svg` : une cible plus ambitieuse pour une activité commerciale importante.
- `industrialisation.md` : les choix, limites et sources de cette cible future.
- `aws-service-symbols.svg` : les logos officiels AWS embarqués localement pour rendre le schéma reproductible, sans chargement d’images externes.

La cible d’industrialisation ajoute notamment Aurora, cache et secours multi-région. Ces services ne sont pas déployés par le Terraform hybride.

Le schéma hybride représente la configuration Terraform actuelle, sans domaine personnalisé : CloudFront fournit l’adresse HTTPS et rejoint un ALB interne dans les sous-réseaux privés via une origine VPC. Le flux privé CloudFront → ALB utilise HTTP. La configuration affichée est le mode réduit avec une EC2 désirée, un maximum de deux EC2, RDS Single-AZ et un NAT. Le bas du schéma explique l’option haute disponibilité.

La Lambda d’administration pour les migrations SQL est représentée dans une section distincte. Elle prépare les tables au démarrage et ne participe pas au traitement des commandes. Le publisher partage les EC2 de l’API, dans un service séparé. Les renvois `D1` pointent tous vers le même RDS ; les sections regroupent les flux et ne définissent pas des réseaux supplémentaires. Les détails de la configuration actuelle se trouvent dans le [README infrastructure](../../infrastructure/readme.md).

Pour régénérer le SVG et le PNG depuis la racine : `npm ci`, puis `npm run diagram` (avec l’environnement Python du projet installé). Le script lit `high_availability` et `monthly_budget_usd` dans le fichier local de configuration ; toute modification de topologie demande aussi une mise à jour explicite du script de dessin. Le schéma représente du code préparé, sans affirmer qu’une infrastructure AWS est déployée.

Les logos proviennent du [paquet officiel d’icônes d’architecture AWS](https://aws.amazon.com/architecture/icons/), édition du 31 juillet 2026. Les tracés originaux sont conservés dans le catalogue SVG ; seuls leur taille et leur placement changent dans le schéma.
