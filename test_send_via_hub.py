#!/usr/bin/env python3
"""
Test d'envoi de message via le transport EventSub (via IPC Hub).

Ce script simule une commande qui envoie un message via le MessageBus,
afin de vérifier que _log_send_result() capture bien les drops.
"""

import asyncio
import socket
import json
import time
import random

def send_ipc_message(message_dict):
    """Envoie un message via le socket IPC du Hub."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect('/tmp/kissbot_hub.sock')
        
        # Sérialiser et envoyer
        msg_json = json.dumps(message_dict)
        sock.sendall(msg_json.encode())
        sock.close()
        
        print(f"✅ Message IPC envoyé: {message_dict}")
        return True
    except Exception as e:
        print(f"❌ Erreur IPC: {e}")
        return False


def main():
    """
    Envoie un message "chat.outbound" via le Hub IPC.
    
    Le Hub le transmettra au transport EventSubChatClient,
    qui appelle _log_send_result() pour logger le résultat.
    """
    
    # Message outbound avec contenu qui sera bloqué par AutoMod
    msg_id = random.randint(10000, 99999)
    timestamp = int(time.time())
    
    message = {
        "type": "chat.outbound",
        "data": {
            "channel": "serda_bot",
            "text": f"🧪 Test IPC AutoMod detection [#{msg_id}@{timestamp}]",
            "reply_to": None
        }
    }
    
    print("📤 Envoi message via IPC Hub...")
    send_ipc_message(message)
    
    print("\n💡 Vérifiez les logs avec:")
    print("   tail -50 logs/broadcast/serda_bot/instance.log | grep -A 2 'AutoMod\\|msg_rejected\\|_log_send_result'")


if __name__ == "__main__":
    main()
