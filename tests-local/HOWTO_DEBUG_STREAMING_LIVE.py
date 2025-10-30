"""
🎬 GUIDE: Voir streaming en live pendant que le bot tourne

1. Activer debug dans config.yaml:
   llm:
     stream_response_debug: "on"

2. Lancer le bot:
   python main.py

3. Dans Twitch chat, taper:
   !joke

4. Regarder la console du bot:
   🌊 [STREAMING START] Pourquoi les... [chunks arrivent] ... [STREAMING END]

5. Dans Twitch chat, voir:
   @user Pourquoi les développeurs confondent Halloween et Noël ? Parce que Oct 31 == Dec 25 !

RÉSULTAT:
- Console: Chunks progressifs (debug)
- Twitch: Message complet (pas de spam)
"""

print(__doc__)
