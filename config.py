import os
import sys

# --- FONCTION UTILITAIRE POUR LA CONVERSION ---
def get_env_var(name, default=None, is_int=False):
    """Récupère une variable d'environnement et gère la conversion de type et les erreurs."""
    value = os.getenv(name, default)
    if value is None or value == "":
        # Si la variable n'est pas trouvée (cas Render manquant), on laisse la valeur par défaut (souvent None)
        return default
        
    if is_int:
        try:
            return int(value)
        except ValueError:
            # Si l'ID est fourni mais n'est pas un nombre, on affiche une erreur et s'arrête
            print(f"FATAL ERROR: Environment variable '{name}' must be an integer.")
            sys.exit(1)
            
    return value

# --- 1. CONFIGURATION OBLIGATOIRE DU BOT TELEGRAM (Lue depuis l'environnement) ---

# 🔑 API ID : Récupération depuis l'environnement, doit être un entier
API_ID = get_env_var("API_ID", default=0, is_int=True)

# 🔑 API Hash : Récupération depuis l'environnement
API_HASH = get_env_var("API_HASH", default="")

# 🔑 Bot Token : Récupération depuis l'environnement
BOT_TOKEN = get_env_var("BOT_TOKEN", default="")

# 👑 ID de l'administrateur (peut être lu depuis l'environnement ou fixé)
# Si vous le fixez ici, il ne sera pas écrasé par l'environnement
ADMIN_ID = 7196268478


# --- 2. CONFIGURATION DES CANAUX (Fixées ou lues) ---

# ➡️ ID du canal SOURCE
SOURCE_CHANNEL_ID = -1001003464313784 

# ⬅️ ID du canal PRÉDICTION
PREDICTION_CHANNEL_ID = -1003300736833

# --- 3. CONFIGURATION DU SERVEUR WEB ---
# Lit le port de l'environnement (essentiel pour Render)
PORT = int(os.environ.get("PORT", 8080))

# --- 4. CONFIGURATION DES COULEURS (Cartes) ---

ALL_SUITS = ['♠', '♣', '♦', '♥']

SUIT_DISPLAY = {
    '♠': 'Pique', 
    '♣': 'Trèfle', 
    '♦': 'Carreau', 
    '♥': 'Cœur'
}

# Mappage pour l'ancienne logique (à définir si besoin, sinon vide)
SUIT_MAPPING = {} 
    
