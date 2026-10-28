# Les workflows : des vérifications automatiques

`ci.yml` s’exécute sur les push, les pull requests et sur demande depuis GitHub Actions.

Il prépare Python, Node.js et PostgreSQL, puis vérifie le style, les README, les tests, la construction des archives et Terraform. Les archives EC2 et Lambda sont conservées sept jours comme résultats téléchargeables.

Les tests Terraform utilisent un fournisseur simulé. Le workflow ne crée pas de ressources AWS et ne peut pas démontrer que les permissions d’un compte réel sont correctes.

Un changement de code doit conserver cette chaîne au vert avant d’être déployé. La validation CI ne remplace pas la revue du plan Terraform.
