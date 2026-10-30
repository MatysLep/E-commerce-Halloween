# Les versions de la base

`0001_initial_order_audit_and_outbox_schema.py` crée les tables initiales, leurs liens, les index et les contraintes de stock et de montant.

`0002_local_accounts.py` ajoute les comptes locaux et les sessions pour l’inscription et la connexion sans Cognito en mode local.

La fonction `upgrade` applique la version ; `downgrade` décrit son retrait. Le retrait de la première version supprime les tables : ne l’exécutez pas sur une base contenant des données à conserver.

Les fichiers restent indépendants des modèles Python actuels. Ainsi, une ancienne migration continue de décrire exactement la même structure lorsque l’application évolue.
