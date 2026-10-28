# Le frontend : ce que voit le client

Ce dossier contient une boutique responsive, c’est-à-dire adaptée au téléphone comme à l’ordinateur. Il utilise HTML, CSS et JavaScript natifs : aucun framework à installer dans le navigateur.

| Fichier      | Explication                                                                |
| ------------ | -------------------------------------------------------------------------- |
| `index.html` | Les zones de la page : catalogue, panier et commandes.                     |
| `styles.css` | Les couleurs, les espacements et l’adaptation aux écrans.                  |
| `app.js`     | Les interactions, les appels API et l’actualisation des commandes.         |
| `auth.js`    | La connexion Cognito avec code temporaire, PKCE et vérification du retour. |
| `cart.mjs`   | Les petits calculs de panier, vérifiables avec les tests Node.js.          |
| `config.js`  | La configuration publique ; remplacée dans S3 lors du déploiement.         |

Le panier et la clé de tentative sont conservés dans `localStorage`. Le jeton de session est dans `sessionStorage` et disparaît à la fermeture de l’onglet. Il n’est jamais placé dans les fichiers du projet. Après expiration, il faut se reconnecter.

PKCE lie le retour de connexion au navigateur qui l’a demandé. Le serveur continue de vérifier chaque jeton : cacher un bouton ne constitue pas une protection.

Le navigateur n’envoie que des identifiants de produits et des quantités. Les prix et les droits sont toujours contrôlés par l’API. Les contenus venant de l’API sont affichés comme du texte, sans insertion de HTML.

Lancer la page avec `docker compose up --build -d` ou `make serve` depuis la racine. Ne l’ouvrez pas directement comme un fichier : les modules JavaScript et les routes API nécessitent un serveur HTTP.

`npm run format` formate les sources ; `npm test` vérifie les calculs. Sur AWS, les fichiers sont privés dans S3 et distribués par CloudFront.
