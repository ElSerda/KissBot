"""
📏 CONSTANTES SYNAPSES - Source unique de vérité

Centralise toutes les limites de caractères/tokens pour Twitch et LLM.
Utilisé par CloudSynapse et LocalSynapse.
"""

# ═══════════════════════════════════════════════════════════════════
# 🎮 TWITCH IRC LIMITS
# ═══════════════════════════════════════════════════════════════════
TWITCH_MAX_CHARS = 500          # Limite absolue Twitch IRC

# ═══════════════════════════════════════════════════════════════════
# 🤖 COMMANDE !ask - Réponses détaillées
# ═══════════════════════════════════════════════════════════════════
ASK_PREFIX = "[ASK] "           # Préfixe des réponses !ask
ASK_PREFIX_LEN = 6              # len("[ASK] ")
ASK_TARGET_CHARS = 419          # Content max (500 - 6 - 15% marge)
ASK_PROMPT_RANGE = "350-420"    # Guidage LLM dans prompt système
ASK_MAX_TOKENS_CLOUD = 190      # Tokens OpenAI (~400 chars @ 2.1 ratio, marge sécurité)
ASK_MAX_TOKENS_LOCAL = 120      # Tokens Mistral local (~250 chars)

# ═══════════════════════════════════════════════════════════════════
# 💬 MENTIONS - Réponses courtes/fun
# ═══════════════════════════════════════════════════════════════════
MENTION_MAX_CHARS = 150         # Limite pour mentions
MENTION_MAX_TOKENS = 200        # Tokens pour mentions

# ═══════════════════════════════════════════════════════════════════
# 🎭 GEN_LONG - Générations longues (Mistral local)
# ═══════════════════════════════════════════════════════════════════
GEN_LONG_MAX_CHARS = 400        # Hard truncate pour gen_long
GEN_LONG_MAX_TOKENS = 100       # Tokens Mistral

# ═══════════════════════════════════════════════════════════════════
# 😂 JOKES - Blagues
# ═══════════════════════════════════════════════════════════════════
JOKE_MAX_TOKENS = 150           # Tokens pour blagues

# ═══════════════════════════════════════════════════════════════════
# 🔧 VALIDATION
# ═══════════════════════════════════════════════════════════════════
def validate_constants():
    """Vérifie la cohérence des constantes au démarrage."""
    assert ASK_PREFIX_LEN == len(ASK_PREFIX), f"ASK_PREFIX_LEN mismatch: {ASK_PREFIX_LEN} != {len(ASK_PREFIX)}"
    assert ASK_TARGET_CHARS + ASK_PREFIX_LEN <= TWITCH_MAX_CHARS, "ASK overflow Twitch limit!"
    margin = TWITCH_MAX_CHARS - ASK_TARGET_CHARS - ASK_PREFIX_LEN
    margin_pct = margin / TWITCH_MAX_CHARS * 100
    assert margin_pct >= 10, f"Margin too low: {margin_pct:.1f}%"
    return True

# Auto-validation à l'import
validate_constants()
