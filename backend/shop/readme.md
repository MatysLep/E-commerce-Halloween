# Le code de la boutique

Chaque fichier a une responsabilité précise pour éviter un gros fichier qui ferait tout.

| Fichier | Son rôle |
| --- | --- |
| `domain.py` | Le vocabulaire métier et les règles du panier, sans dépendance à AWS. |
| `orders.py` | Créer une commande, vérifier le stock et gérer les nouvelles tentatives. |
| `models.py` | Décrire les tables : produits, commandes, lignes, événements, outbox et reçus. |
| `database.py` | Ouvrir les connexions SQL ; lire les secrets et vérifier TLS sur AWS. |
| `api.py` | Recevoir les requêtes HTTP et renvoyer des réponses compréhensibles. |
| `local_accounts.py` | Gérer les comptes locaux, le hachage des mots de passe et les sessions révocables. |
| `auth.py` | Vérifier la connexion Cognito et l’identité du client. |
| `events.py` | Réaliser l’emballage, l’expédition et la notification une seule fois en base. |
| `publisher.py` | Envoyer les événements en attente, puis réessayer après un échec. |
| `handlers.py` | Adapter les messages SQS aux traitements métier des Lambdas. |
| `migration_handler.py` | Préparer la base sur AWS avec un compte administrateur isolé. |
| `cli.py` | Les commandes d’administration : `init`, `status`, `replay`. |
| `seed.py` | Ajouter les douze produits de démonstration sans réinitialiser leur stock. |
| `config.py` | Lire et contrôler la configuration. |

Une **transaction** est un groupe d’écritures indivisible. Une **outbox** est une boîte de départ enregistrée en base, qui évite de perdre un événement si SNS est indisponible. L’**idempotence** signifie qu’une même action reçue plusieurs fois ne produit qu’un seul résultat métier.

Les fonctions métier reçoivent leurs dépendances (`factory`, fonction d’envoi d’email). Les tests peuvent donc simuler une panne sans compte AWS. Les prix sont des nombres entiers de centimes ; on n’utilise pas de nombres décimaux approximatifs pour calculer une commande.

Les événements ne contiennent pas d’email. Le consommateur de notification retrouve le destinataire dans la commande. Les logs enregistrent les identifiants techniques, pas les jetons ou les adresses email.
