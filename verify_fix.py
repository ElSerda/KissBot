#!/usr/bin/env python3
"""
Test rapide pour vérifier que le moderator_id est maintenant le bot (1209350837)
"""

import re

# Lire la fonction cmd_kbupdate
with open("/home/serda/Project/KissBot-standalone/modules/classic_commands/broadcaster_commands/broadcast.py", "r") as f:
    content = f.read()

# Chercher la ligne avec send_chat_announcement
match = re.search(r'await twitch_client\.send_chat_announcement\(\s*broadcaster_id=msg\.channel_id,\s*moderator_id=([^,]+),', content)

if match:
    moderator_id_param = match.group(1).strip()
    print(f"✅ moderator_id trouvé: {moderator_id_param}")
    
    if "1209350837" in moderator_id_param:
        print(f"✅ C'EST CORRECT ! moderator_id est le bot (1209350837)")
    elif "msg.user_id" in moderator_id_param:
        print(f"❌ PROBLÈME : moderator_id est toujours msg.user_id (el_serda)")
    else:
        print(f"❓ moderator_id: {moderator_id_param}")
else:
    print("❌ send_chat_announcement not found!")
