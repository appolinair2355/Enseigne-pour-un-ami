🤖 Bot de Prédiction Baccarat - Mode Planification Manuelle
Ce bot Telegram surveille un canal source, attend les entrées de prédictions planifiées par un administrateur, puis déclenche automatiquement l'envoi de ces prédictions vers un canal cible dès la détection d'un jeu clé.
⚙️ Prérequis
Avant de lancer le bot, vous devez vous assurer d'avoir les éléments suivants :
Python 3.8+
Bibliothèques requises : Telethon, aiohttp (installez-les via pip install telethon aiohttp).
Un compte Telegram (pour obtenir l'API ID/Hash).
Un Bot Telegram (créé via @BotFather).
L'accès administrateur aux canaux Source et Prédiction.
🛠️ Configuration et Lancement
🚀 Fonctionnement et Logique de Déclenchement
Le bot opère en mode planification manuelle :
1. Planification Manuelle
L'administrateur utilise la commande /plan_predictions dans le chat privé du bot pour saisir le numéro du jeu (P) et la couleur prédite (ex: 1250,♠).
2. Déclenchement Automatique (Clé 🔑)
Le bot surveille le canal source. Dès qu'il reçoit un message (même non finalisé, c'est-à-dire sans le ✅ ou ❌) pour le jeu P-1 (le jeu précédant le jeu planifié P), il exécute les actions suivantes :
Il récupère la prédiction P planifiée par l'administrateur.
Il vérifie les règles de stock et de proximité.
Il envoie la prédiction au canal cible.
3. Règles d'Envoi et de Stockage
Stock Actif Maximum : Le bot ne maintient que 2 prédictions actives à la fois (celles déjà envoyées).
Distance de Proximité : Une prédiction en file d'attente est envoyée lorsque la distance est de 2 ou 3 jeux par rapport au jeu actuel.
Format du Message de Prédiction Initial : 📲Game: [N° Jeu]:[Couleur] statut :🔮 1️⃣
4. Vérification du Statut (Finalisation)
La mise à jour du statut (✅ ou ❌) se fait uniquement lorsque le bot reçoit le message du jeu P (le jeu prédit) qui est finalisé (contenant ✅ ou ❌).
Vérification : Le bot vérifie si la couleur prédite est présente dans le deuxième groupe du message source (la main du Banquier).
Format du Message Final : 📲Game: [N° Jeu]:[Couleur] statut :✅
👑 Commandes Administrateur
Toutes les commandes doivent être envoyées dans le chat privé avec le bot.
/plan_predictions : Lance le mode interactif pour ajouter, supprimer ou enregistrer les prédictions (Jeu P et Couleur).
/status : Affiche l'état du bot : jeu actuel, prédictions planifiées, actives (envoyées), et en file d'attente.
/stop_transfert : Active/Désactive l'envoi des messages bruts du canal source vers votre chat administrateur.
/help : Affiche le guide de fonctionnement.
⚠️ Notes Techniques
Le reset quotidien (effacement des stocks, file d'attente et plans) est programmé tous les jours à 00h59 WAT.
Le code utilise le deuxième groupe entre parenthèses du message source pour la vérification du résultat (main du Banquier).
🚀 Fonctionnement et Logique de Déclenchement
Le bot opère en mode planification manuelle :
1. Planification Manuelle
L'administrateur utilise la commande /plan_predictions dans le chat privé du bot pour saisir le numéro du jeu (P) et la couleur prédite (ex: 1250,♠).
2. Déclenchement Automatique (Clé 🔑)
Le bot surveille le canal source. Dès qu'il reçoit un message (même non finalisé, c'est-à-dire sans le ✅ ou ❌) pour le jeu P-1 (le jeu précédant le jeu planifié P), il exécute les actions suivantes :
Il récupère la prédiction P planifiée par l'administrateur.
Il vérifie les règles de stock et de proximité.
Il envoie la prédiction au canal cible.
3. Règles d'Envoi et de Stockage
Stock Actif Maximum : Le bot ne maintient que 2 prédictions actives à la fois (celles déjà envoyées).
Distance de Proximité : Une prédiction en file d'attente est envoyée lorsque la distance est de 2 ou 3 jeux par rapport au jeu actuel.
Format du Message de Prédiction Initial : 📲Game: [N° Jeu]:[Couleur] statut :🔮 1️⃣
4. Vérification du Statut (Finalisation)
La mise à jour du statut (✅ ou ❌) se fait uniquement lorsque le bot reçoit le message du jeu P (le jeu prédit) qui est finalisé (contenant ✅ ou ❌).
Vérification : Le bot vérifie si la couleur prédite est présente dans le deuxième groupe du message source (la main du Banquier).
Format du Message Final : 📲Game: [N° Jeu]:[Couleur] statut :✅
👑 Commandes Administrateur
Toutes les commandes doivent être envoyées dans le chat privé avec le bot.
/plan_predictions : Lance le mode interactif pour ajouter, supprimer ou enregistrer les prédictions (Jeu P et Couleur).
/status : Affiche l'état du bot : jeu actuel, prédictions planifiées, actives (envoyées), et en file d'attente.
/stop_transfert : Active/Désactive l'envoi des messages bruts du canal source vers votre chat administrateur.
/help : Affiche le guide de fonctionnement.
⚠️ Notes Techniques
Le reset quotidien (effacement des stocks, file d'attente et plans) est programmé tous les jours à 00h59 WAT.
Le code utilise le deuxième groupe entre parenthèses du message source pour la vérification du résultat (main du Banquier).
