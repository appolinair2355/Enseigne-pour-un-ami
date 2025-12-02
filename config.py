import os

# --- 1. CONFIGURATION OBLIGATOIRE DU BOT TELEGRAM ---
# REMPLACEZ TOUTES LES VALEURS ENTRE GUILLEMETS OU LE '0' PAR VOS PROPRES INFORMATIONS.

# 🔑 API ID (obtenu via my.telegram.org)
API_ID = 0 # REMPLACER PAR VOTRE API ID (int)

# 🔑 API Hash (obtenu via my.telegram.org)
API_HASH = "VOTRE_API_HASH" # REMPLACER PAR VOTRE API HASH (str)

# 🔑 Bot Token (obtenu via @BotFather)
BOT_TOKEN = "VOTRE_BOT_TOKEN" # REMPLACER PAR VOTRE TOKEN (str)

# 👑 ID de l'administrateur
ADMIN_ID = 7196268478


# --- 2. CONFIGURATION DES CANAUX ---

# ➡️ ID du canal SOURCE (où les messages sont lus)
SOURCE_CHANNEL_ID = -1001003464313784 

# ⬅️ ID du canal PRÉDICTION (où le bot envoie les prédictions)
PREDICTION_CHANNEL_ID = -1003300736833

# --- 3. CONFIGURATION DU SERVEUR WEB ---
# Utilisé pour le déploiement.
PORT = int(os.environ.get("PORT", 8080))

# --- 4. CONFIGURATION DES COULEURS (Cartes) ---

# Liste de toutes les couleurs (Pique, Trèfle, Carreau, Cœur)
ALL_SUITS = ['♠', '♣', '♦', '♥']

# Mappage pour l'affichage (non essentiel pour la logique actuelle, mais nécessaire pour l'import)
SUIT_DISPLAY = {
    '♠': 'Pique', 
    '♣': 'Trèfle', 
    '♦': 'Carreau', 
    '♥': 'Cœur'
}

# Mappage de couleur (placeholder)
SUIT_MAPPING = {} 
