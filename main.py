import os
import asyncio
import re
import logging
import sys
from datetime import datetime, timedelta, timezone, time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiohttp import web
# Assurez-vous d'avoir les variables SOURCE_CHANNEL_ID et PREDICTION_CHANNEL_ID dans config.py
from config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_ID,
    SOURCE_CHANNEL_ID, PREDICTION_CHANNEL_ID, PORT,
    SUIT_MAPPING, ALL_SUITS, SUIT_DISPLAY
)

# --- Configuration et Initialisation ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Vérifications minimales de la configuration
if not API_ID or API_ID == 0:
    logger.error("API_ID manquant")
    exit(1)
if not API_HASH:
    logger.error("API_HASH manquant")
    exit(1)
if not BOT_TOKEN:
    logger.error("BOT_TOKEN manquant")
    exit(1)

logger.info(f"Configuration: SOURCE_CHANNEL={SOURCE_CHANNEL_ID}, PREDICTION_CHANNEL={PREDICTION_CHANNEL_ID}")

# Initialisation du client Telegram avec session string ou nouvelle session
session_string = os.getenv('TELEGRAM_SESSION', '')
client = TelegramClient(StringSession(session_string), API_ID, API_HASH)

# --- Variables Globales d'État ---
pending_predictions = {}
queued_predictions = {}
recent_games = {}
processed_messages = set()
last_transferred_game = None
current_game_number = 0

# Nouvel état pour les prédictions planifiées manuellement par l'admin
PLANNED_PREDICTIONS = {} # Format: {game_number_P: '♠', ...}
planning_session = {} # État temporaire pour la commande /plan_predictions

last_processed_game_data = None 

MAX_PENDING_PREDICTIONS = 2  # Nombre maximal de prédictions actives
PROXIMITY_THRESHOLD = 3      # Nombre de jeux avant l'envoi depuis la file d'attente (distance 3 ou 2)

# Le délai 'a' n'est plus pertinent pour la génération, mais conservé pour les commandes de statut
PREDICTION_DELAY = 1         

source_channel_ok = False
prediction_channel_ok = False
transfer_enabled = True # Initialisé à True. Contrôlé par /stop_transfert

# --- Fonctions d'Analyse ---

def extract_game_number(message: str):
    """Extrait le numéro de jeu du message."""
    match = re.search(r"#N\s*(\d+)\.?", message, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def extract_parentheses_groups(message: str):
    """Extrait le contenu entre parenthèses."""
    return re.findall(r"\(([^)]*)\)", message)

def normalize_suits(group_str: str) -> str:
    """Normalise les symboles de couleur."""
    normalized = group_str.replace('❤️', '♥').replace('❤', '♥').replace('♥️', '♥')
    normalized = normalized.replace('♠️', '♠').replace('♦️', '♦').replace('♣️', '♣')
    return normalized

def get_suits_in_group(group_str: str):
    """Liste toutes les couleurs (suits) présentes dans une chaîne."""
    normalized = normalize_suits(group_str)
    return [s for s in ALL_SUITS if s in normalized]

def has_suit_in_group(group_str: str, target_suit: str) -> bool:
    """Vérifie si la couleur cible est présente dans le groupe ciblé."""
    normalized = normalize_suits(group_str)
    target_normalized = normalize_suits(target_suit)
    for suit in ALL_SUITS:
        if suit in target_normalized and suit in normalized:
            return True
    return False

def is_message_finalized(message: str) -> bool:
    """Vérifie si le message est un résultat final (non en cours)."""
    if '⏰' in message:
        return False
    return '✅' in message or '🔰' in message

# --- Logique de Prédiction et File d'Attente ---

async def send_prediction_to_channel(target_game: int, predicted_suit: str, base_game: int):
    """Envoie la prédiction au canal de prédiction (Nouveau Format)."""
    try:
        # NOUVEAU FORMAT DE MESSAGE INITIAL
        prediction_msg = f"""📲Game: {target_game}:{predicted_suit} statut :🔮 1️⃣"""

        msg_id = 0

        if PREDICTION_CHANNEL_ID and PREDICTION_CHANNEL_ID != 0 and prediction_channel_ok:
            try:
                pred_msg = await client.send_message(PREDICTION_CHANNEL_ID, prediction_msg)
                msg_id = pred_msg.id
                logger.info(f"✅ Prédiction envoyée au canal de prédiction {PREDICTION_CHANNEL_ID}")
            except Exception as e:
                logger.error(f"❌ Erreur envoi prédiction au canal: {e}")
        else:
            logger.warning(f"⚠️ Canal de prédiction non accessible, prédiction non envoyée")

        pending_predictions[target_game] = {
            'message_id': msg_id,
            'suit': predicted_suit,
            'base_game': base_game,
            'status': '🔮',
            'check_count': 1, # Initialisation à 1
            'created_at': datetime.now().isoformat()
        }

        logger.info(f"Prédiction active: Jeu #{target_game} - {predicted_suit} (basé sur #{base_game})")
        return msg_id

    except Exception as e:
        logger.error(f"Erreur envoi prédiction: {e}")
        return None

def queue_prediction(target_game: int, predicted_suit: str, base_game: int):
    """Met une prédiction en file d'attente pour un envoi différé (gestion du stock)."""
    if target_game in queued_predictions or target_game in pending_predictions:
        logger.info(f"Prédiction #{target_game} déjà en file ou active, ignorée")
        return False

    queued_predictions[target_game] = {
        'target_game': target_game,
        'predicted_suit': predicted_suit,
        'base_game': base_game,
        'queued_at': datetime.now().isoformat()
    }
    logger.info(f"📋 Prédiction #{target_game} mise en file d'attente (sera envoyée quand proche)")
    return True

async def check_and_send_queued_predictions(current_game: int):
    """Vérifie la file d'attente et envoie si la distance est de 2 ou 3 jeux."""
    global current_game_number
    current_game_number = current_game

    sorted_queued = sorted(queued_predictions.keys())

    for target_game in sorted(sorted_queued):
        
        distance = target_game - current_game

        # --- RÈGLE DE SUPPRESSION (DISTANCE 1 OU 0 MANQUÉE) ---
        if distance <= 1: 
            logger.warning(f"⚠️ Prédiction #{target_game} est à une distance {distance}. Fenêtre d'envoi manquée. Supprimée.")
            queued_predictions.pop(target_game, None)
            continue 
        
        # --- RÈGLE D'ENVOI (DISTANCE 2 ou 3) ---
        if len(pending_predictions) >= MAX_PENDING_PREDICTIONS:
            logger.info(f"⏸️ Stock actif plein ({len(pending_predictions)}/{MAX_PENDING_PREDICTIONS}), prédiction #{target_game} reste en file.")
            continue
        
        if distance <= PROXIMITY_THRESHOLD and distance > 1: 
            pred_data = queued_predictions.pop(target_game)
            logger.info(f"🎯 Jeu #{current_game} - Prédiction #{target_game} proche ({distance} jeux), envoi maintenant!")

            await send_prediction_to_channel(
                pred_data['target_game'],
                pred_data['predicted_suit'],
                pred_data['base_game']
            )

async def update_prediction_status(game_number: int, new_status: str):
    """Met à jour le message de prédiction dans le canal et son statut interne (Format Final)."""
    try:
        if game_number not in pending_predictions:
            return False

        pred = pending_predictions[game_number]
        message_id = pred['message_id']
        suit = pred['suit']

        # NOUVEAU FORMAT DE MESSAGE FINAL
        updated_msg = f"""📲Game: {game_number}:{suit} statut :{new_status}"""

        if PREDICTION_CHANNEL_ID and PREDICTION_CHANNEL_ID != 0 and message_id > 0 and prediction_channel_ok:
            try:
                await client.edit_message(PREDICTION_CHANNEL_ID, message_id, updated_msg)
                logger.info(f"✅ Prédiction #{game_number} mise à jour dans le canal: {new_status}")
            except Exception as e:
                logger.error(f"❌ Erreur mise à jour dans le canal: {e}")

        pred['status'] = new_status
        logger.info(f"Prédiction #{game_number} mise à jour: {new_status}")

        # Les prédictions terminées sont supprimées du stock actif
        if new_status in ['✅', '❌']:
            del pending_predictions[game_number]
            logger.info(f"Prédiction #{game_number} terminée et supprimée")

        return True

    except Exception as e:
        logger.error(f"Erreur mise à jour prédiction: {e}")
        return False

async def check_prediction_result(game_number: int, banker_group: str):
    """Vérifie les résultats des prédictions actives (Jeu P) en utilisant la main du Banquier (deuxième groupe)."""
    
    if game_number in pending_predictions:
        pred = pending_predictions[game_number]
        target_suit = pred['suit']

        # Utilisation du groupe du Banquier pour la validation
        if has_suit_in_group(banker_group, target_suit): 
            await update_prediction_status(game_number, '✅')
            return True
        else:
            await update_prediction_status(game_number, '❌')
            return False

    return None
# Continuité du code de la partie 1/2

async def process_finalized_message(message_text: str, chat_id: int):
    """Traite un message pour le déclenchement (P-1, non finalisé) et la vérification (P, finalisé)."""
    global last_transferred_game, current_game_number, last_processed_game_data
    try:
        game_number = extract_game_number(message_text)
        if game_number is None:
            return

        current_game_number = game_number
        message_hash = f"{game_number}_{message_text[:50]}"
        if message_hash in processed_messages:
            return
        processed_messages.add(message_hash)

        if len(processed_messages) > 200:
            processed_messages.clear()

        groups = extract_parentheses_groups(message_text)
        if len(groups) < 2: 
            banker_group = ""
        else:
            # Le Banquier est dans le deuxième groupe (groups[1])
            banker_group = groups[1] 

        # --- Transfert à l'administrateur (si activé) ---
        if transfer_enabled and ADMIN_ID and ADMIN_ID != 0 and last_transferred_game != game_number:
            try:
                transfer_msg = f"📨 **Message reçu du canal source (Finalisé: {is_message_finalized(message_text)}):**\n\n{message_text}"
                await client.send_message(ADMIN_ID, transfer_msg)
                last_transferred_game = game_number
            except Exception as e:
                logger.error(f"❌ Erreur transfert à votre bot: {e}")
        
        # --- LOGIQUE DE DÉCLENCHEMENT DES PRÉDICTIONS PLANIFIÉES (Basée sur P-1) ---
        # Cette logique s'exécute pour TOUS les messages du canal source (non finalisés ou finalisés)
        game_to_trigger = game_number + 1
        
        if game_to_trigger in PLANNED_PREDICTIONS:
            
            target_suit = PLANNED_PREDICTIONS.pop(game_to_trigger)
            
            # Logique pour extraire la première carte de P-1 (pour le journal)
            first_banker_suit_match = re.search(r"[♠♣♦♥]", normalize_suits(banker_group))
            trigger_suit_info = first_banker_suit_match.group(0) if first_banker_suit_match else "N/A"
            
            logger.info(f"🚨 DÉCLENCHEMENT PLANIFIÉ: Jeu P-1=#{game_number} reçu (Banquier commence par {trigger_suit_info}) -> Envoi de P=#{game_to_trigger} ({target_suit})")
            
            queue_prediction(
                game_to_trigger,
                target_suit,
                game_number # P-1 est le jeu de base
            )
            await check_and_send_queued_predictions(game_number) 
        
        # --- VÉRIFICATION DU STATUT (UNIQUEMENT POUR MESSAGES FINALISÉS) ---
        
        if not is_message_finalized(message_text):
            # Le reste du traitement ne concerne que la vérification finale (statut)
            return

        # Le message est finalisé : nous vérifions le statut du jeu P (game_number)
        
        # 1. Vérification des résultats existants (Jeu cible P)
        await check_prediction_result(game_number, banker_group) 

        # 2. Envoi des prédictions en file d'attente (si proche)
        await check_and_send_queued_predictions(game_number)

        # 3. Stockage (pour journal/debug)
        suits_current = set(get_suits_in_group(banker_group))
        last_processed_game_data = {
            'game_number': game_number,
            'banker_group': banker_group, 
            'suits': suits_current
        }

        recent_games[game_number] = {
            'banker_group': banker_group,
            'timestamp': datetime.now().isoformat()
        }
        if len(recent_games) > 100:
            oldest = min(recent_games.keys())
            del recent_games[oldest]

    except Exception as e:
        logger.error(f"Erreur traitement message: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
# --- Gestion des Messages (Hooks Telethon) ---

@client.on(events.NewMessage())
async def handle_message(event):
    """Gère les nouveaux messages dans le canal source et la saisie admin."""
    
    # Gestion de la saisie admin pour la planification
    if event.is_private and event.sender_id == ADMIN_ID:
        await capture_plan_input(event)

    # Traitement des messages du canal source (Doit traiter TOUS les messages pour le trigger P-1)
    try:
        chat = await event.get_chat()
        chat_id = chat.id if hasattr(chat, 'id') else event.chat_id
        if chat_id > 0 and hasattr(chat, 'broadcast') and chat.broadcast:
            chat_id = -1000000000000 - chat_id

        if chat_id == SOURCE_CHANNEL_ID:
            message_text = event.message.message
            await process_finalized_message(message_text, chat_id)

    except Exception as e:
        logger.error(f"Erreur handle_message: {e}")

@client.on(events.MessageEdited())
async def handle_edited_message(event):
    """Gère les messages édités dans le canal source (essentiel pour le statut final)."""
    try:
        chat = await event.get_chat()
        chat_id = chat.id if hasattr(chat, 'id') else event.chat_id
        if chat_id > 0 and hasattr(chat, 'broadcast') and chat.broadcast:
            chat_id = -1000000000000 - chat_id

        if chat_id == SOURCE_CHANNEL_ID:
            message_text = event.message.message
            await process_finalized_message(message_text, chat_id)

    except Exception as e:
        logger.error(f"Erreur handle_edited_message: {e}")

# --- Commandes Administrateur et Planification ---

@client.on(events.NewMessage(pattern='/start'))
async def cmd_start(event):
    if event.is_group or event.is_channel: return
    await event.respond("🤖 **Bot de Prédiction Baccarat**\n\nCommandes: `/status`, `/help`, `/plan_predictions`, `/stop_transfert`")

@client.on(events.NewMessage(pattern='/status'))
async def cmd_status(event):
    if event.is_group or event.is_channel: return
    if event.sender_id != ADMIN_ID and ADMIN_ID != 0:
        await event.respond("Commande réservée à l'administrateur")
        return

    status_msg = f"📊 **État des prédictions:**\n\n🎮 Jeu actuel: #{current_game_number}\n"
    
    if PLANNED_PREDICTIONS:
        status_msg += f"\n**📝 Planifiées ({len(PLANNED_PREDICTIONS)}):**\n"
        for game_num, suit in sorted(PLANNED_PREDICTIONS.items()):
            distance = game_num - current_game_number
            status_msg += f"• Jeu P=#{game_num} ({suit}) - Déclenchement à P-1=#{game_num - 1} (dans {distance} jeux)\n"
    else: status_msg += "\n**📝 Aucune prédiction planifiée**\n"
    
    if pending_predictions:
        status_msg += f"\n**🔮 Actives ({len(pending_predictions)}):**\n"
        for game_num, pred in sorted(pending_predictions.items()):
            distance = game_num - current_game_number
            status_msg += f"• Jeu P=#{game_num} ({pred['suit']}) - Statut: {pred['status']} (basé sur P-1=#{pred['base_game']} - dans {distance} jeux)\n"
    else: status_msg += "\n**🔮 Aucune prédiction active**\n"

    if queued_predictions:
        status_msg += f"\n**📋 En file d'attente ({len(queued_predictions)}):**\n"
        for game_num, pred in sorted(queued_predictions.items()):
            distance = game_num - current_game_number
            status_msg += f"• Jeu P=#{game_num} ({pred['predicted_suit']}) (basé sur P-1=#{pred['base_game']} - dans {distance} jeux)\n"
    else: status_msg += "\n**📋 Aucune prédiction en file**\n"
    
    status_transfert = "Activé" if transfer_enabled else "Désactivé"
    status_msg += f"\n**État du Transfert Admin**: {status_transfert}"
    await event.respond(status_msg)

@client.on(events.NewMessage(pattern='/help'))
async def cmd_help(event):
    if event.is_group or event.is_channel: return

    await event.respond(f"""📖 **Aide - Bot de Prédiction Baccarat**\n
### 🤖 Mode de Fonctionnement (Planification Manuelle)
1.  **Planification**: L'administrateur utilise `/plan_predictions` pour **enregistrer manuellement** le numéro de jeu $P$ et la couleur prédite.
2.  **Déclenchement (Clé)**: Le bot surveille le canal source. Dès qu'il voit un message (même non finalisé) pour le jeu **$P-1$**, il envoie **immédiatement** la prédiction $P$.
3.  **Vérification (Statut)**: Le statut final (✅ ou ❌) est mis à jour **uniquement** lorsque le message du jeu $P$ est reçu et **finalisé**. Le bot vérifie si la couleur prédite est dans le **deuxième groupe (Banquier)**.

### ⚙️ Règles de Stockage/Envoi
1.  Max **{MAX_PENDING_PREDICTIONS}** prédictions actives à la fois (stock).
2.  Envoi depuis la file d'attente **uniquement** si la distance est de **{PROXIMITY_THRESHOLD} ou {PROXIMITY_THRESHOLD - 1} jeux**.
3.  Toute prédiction atteignant la distance **1 ou 0** dans la file est **supprimée** (fenêtre manquée).
\n**Commandes Administrateur:** • `/plan_predictions` : Lance le mode interactif de planification (Ajouter/Supprimer/Enregistrer).
• `/stop_transfert` : Active/Désactive l'envoi des messages sources à l'admin.
• `/status` : Affiche les prédictions planifiées et actives.
""")

@client.on(events.NewMessage(pattern='/stop_transfert'))
async def cmd_stop_transfert(event):
    global transfer_enabled
    if event.is_group or event.is_channel: return
    if event.sender_id != ADMIN_ID and ADMIN_ID != 0:
        await event.respond("Commande réservée à l'administrateur")
        return
    
    transfer_enabled = not transfer_enabled
    status = "Activé" if transfer_enabled else "Désactivé"
    await event.respond(f"✅ **Transfert des messages source à l'admin** : {status}")

# --- Commandes pour la Planification ---

@client.on(events.NewMessage(pattern='/plan_predictions'))
async def cmd_plan_start(event):
    if event.is_group or event.is_channel: return
    if event.sender_id != ADMIN_ID and ADMIN_ID != 0:
        await event.respond("Commande réservée à l'administrateur")
        return

    user_id = event.sender_id
    
    # Affichage du plan actuel au début
    plans_text = "\n".join([f"• #{n}: {s}" for n, s in sorted(PLANNED_PREDICTIONS.items())])
    if not plans_text: plans_text = "Aucune prédiction enregistrée."

    buttons = [
        [events.Button.inline(f'Ajouter N° et Couleur', data='plan_add')],
        [events.Button.inline(f'Supprimer un N°', data='plan_delete')],
        [events.Button.inline('Enregistrer la Saisie', data='plan_save'),
         events.Button.inline('Annuler la Saisie', data='plan_cancel')]
    ]

    await event.respond(
        f"📝 **Planification Manuelle de Prédictions**\n\n**Plans Actifs (Globaux) :**\n{plans_text}",
        buttons=buttons
    )

@client.on(events.CallbackQuery(data=re.compile(r'plan_(add|save|cancel|delete)')))
async def callback_plan_handler(event):
    global PLANNED_PREDICTIONS
    user_id = event.sender_id
    
    if user_id != ADMIN_ID and ADMIN_ID != 0:
        await event.answer("Accès refusé.")
        return

    action = event.pattern_match.group(1)
    
    if action == 'add':
        planning_session[user_id] = planning_session.get(user_id, [])
        await event.edit("Entrez la prédiction au format `N°_JEU,Couleur` (ex: `1250,♠`).")
        await event.answer("Prêt à recevoir la saisie d'ajout...")

    elif action == 'delete':
        await event.edit("Entrez le **N°_JEU** à supprimer (ex: `1250`).")
        # Marquer l'attente pour la suppression
        planning_session[user_id] = 'DELETING' 
        await event.answer("Prêt à recevoir la saisie de suppression...")
        
    elif action == 'save':
        if not planning_session.get(user_id) or planning_session.get(user_id) == 'DELETING':
            await event.edit("❌ Aucune nouvelle prédiction à enregistrer.", buttons=None)
            await event.answer("Rien à enregistrer.")
            return

        new_plans = planning_session.pop(user_id)
        count = 0
        for game_num, suit in new_plans:
            PLANNED_PREDICTIONS[game_num] = suit
            count += 1
            
        await event.edit(f"✅ **{count} prédiction(s) planifiée(s) enregistrée(s).**", buttons=None)
        await event.answer("Prédictions enregistrées.")
        
    elif action == 'cancel':
        planning_session.pop(user_id, None)
        await event.edit("🛑 **Planification annulée.**", buttons=None)
        await event.answer("Annulé.")

@client.on(events.NewMessage())
async def capture_plan_input(event):
    user_id = event.sender_id
    
    if user_id in planning_session and event.message.message and event.is_private:
        text = event.message.message.strip()
        
        if text.startswith('/plan_predictions'): return
        
        # Logique de suppression
        if planning_session.get(user_id) == 'DELETING':
            if text.isdigit():
                game_num = int(text)
                planning_session.pop(user_id) # Fin de la session de suppression
                
                if game_num in PLANNED_PREDICTIONS:
                    del PLANNED_PREDICTIONS[game_num]
                    await event.respond(f"✅ Prédiction #{game_num} **supprimée** du plan.", buttons=None)
                else:
                    await event.respond(f"⚠️ Prédiction #{game_num} non trouvée dans le plan actif.", buttons=None)
            else:
                await event.respond("❌ Veuillez entrer uniquement le numéro de jeu à supprimer.")
            return

        # Logique d'ajout
        match = re.match(r"(\d+),\s*([♠♣♦♥])", text, re.IGNORECASE)
        
        if match:
            game_num = int(match.group(1))
            suit = match.group(2).upper()
            
            if current_game_number > 0 and game_num <= current_game_number:
                await event.respond(f"❌ Impossible de planifier le jeu #{game_num}, le jeu actuel est déjà #{current_game_number}.")
                return
            
            planning_session[user_id].append((game_num, suit))
            
            current_plans = planning_session[user_id]
            plans_text = "\n".join([f"• #{n}: {s}" for n, s in sorted(current_plans)])

            buttons = [
                [events.Button.inline(f'Ajouter N° et Couleur', data='plan_add')],
                [events.Button.inline(f'Supprimer un N°', data='plan_delete')],
                [events.Button.inline('Enregistrer la Saisie', data='plan_save'),
                 events.Button.inline('Annuler la Saisie', data='plan_cancel')]
            ]

            await event.respond(
                f"✅ Prédiction ajoutée : #{game_num} $\\rightarrow$ {suit}.\n\n**Saisie en cours ({len(current_plans)}):**\n{plans_text}",
                buttons=buttons
            )
        else:
            await event.respond("❌ Format incorrect. Veuillez utiliser `N°_JEU,Couleur` (ex: `1250,♠`).")
        

# --- Commandes de Décalage (conservées mais moins pertinentes) ---

@client.on(events.NewMessage(pattern='/setdelay (\d+)'))
async def cmd_setdelay(event):
    global PREDICTION_DELAY
    if event.is_group or event.is_channel: return
    if event.sender_id != ADMIN_ID and ADMIN_ID != 0:
        await event.respond("Commande réservée à l'administrateur")
        return

    try:
        new_delay = int(event.pattern_match.group(1))
        if new_delay <= 0:
            await event.respond("Le délai doit être un entier positif (P = N + a)")
            return
            
        PREDICTION_DELAY = new_delay
        await event.respond(f"✅ **Délai de prédiction (a) mis à jour!**\n(Note: Non utilisé pour la planification manuelle.)")

    except Exception:
        await event.respond("Format invalide. Utilisation: `/setdelay <nombre>`.")

@client.on(events.NewMessage(pattern='/delay'))
async def cmd_getdelay(event):
    if event.is_group or event.is_channel: return
    await event.respond(f"Le délai de prédiction actuel est `a = {PREDICTION_DELAY}`.\n(Note: Non utilisé pour la planification manuelle.)")

# --- Serveur Web et Démarrage ---

async def index(request):
    html = f"""<!DOCTYPE html><html><head><title>Bot Prédiction Baccarat</title></head><body><h1>🎯 Bot de Prédiction Baccarat</h1><p>Le bot est en ligne et surveille les canaux.</p><p><strong>Jeu actuel:</strong> #{current_game_number}</p></body></html>"""
    return web.Response(text=html, content_type='text/html', status=200)

async def health_check(request):
    return web.Response(text="OK", status=200)

async def start_web_server():
    """Démarre le serveur web pour la vérification de l'état (health check)."""
    app = web.Application()
    app.router.add_get('/', index)
    app.router.add_get('/health', health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start() 

async def schedule_daily_reset():
    """Tâche planifiée pour la réinitialisation quotidienne des stocks de prédiction à 00h59 WAT."""
    wat_tz = timezone(timedelta(hours=1)) 
    reset_time = time(0, 59, tzinfo=wat_tz)

    logger.info(f"Tâche de reset planifiée pour {reset_time} WAT.")

    while True:
        now = datetime.now(wat_tz)
        target_datetime = datetime.combine(now.date(), reset_time, tzinfo=wat_tz)
        if now >= target_datetime:
            target_datetime += timedelta(days=1)
            
        time_to_wait = (target_datetime - now).total_seconds()

        logger.info(f"Prochain reset dans {timedelta(seconds=time_to_wait)}")
        await asyncio.sleep(time_to_wait)

        logger.warning("🚨 RESET QUOTIDIEN À 00h59 WAT DÉCLENCHÉ!")
        
        global pending_predictions, queued_predictions, recent_games, processed_messages, last_transferred_game, current_game_number, last_processed_game_data, PLANNED_PREDICTIONS

        pending_predictions.clear()
        queued_predictions.clear()
        recent_games.clear()
        processed_messages.clear()
        PLANNED_PREDICTIONS.clear()
        last_transferred_game = None
        current_game_number = 0
        last_processed_game_data = None
        
        logger.warning("✅ Toutes les données de prédiction ont été effacées.")

async def start_bot():
    """Démarre le client Telegram et les vérifications initiales."""
    global source_channel_ok, prediction_channel_ok
    try:
        await client.start(bot_token=BOT_TOKEN)
        
        source_channel_ok = True
        prediction_channel_ok = True 
        logger.info("Bot connecté et canaux marqués comme accessibles.")
        return True
    except Exception as e:
        logger.error(f"Erreur démarrage du client Telegram: {e}")
        return False

async def main():
    """Fonction principale pour lancer le serveur web, le bot et la tâche de reset."""
    try:
        await start_web_server()

        success = await start_bot()
        if not success:
            logger.error("Échec du démarrage du bot")
            return

        # Lancement de la tâche de reset en arrière-plan
        asyncio.create_task(schedule_daily_reset())
        
        logger.info("Bot complètement opérationnel - En attente de messages...")
        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Erreur dans main: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if client.is_connected():
            await client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot arrêté par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
