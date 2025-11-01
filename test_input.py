#!/usr/bin/env python3
"""
Test simple pour valider le pattern input() avec asyncio
"""
import asyncio


async def worker(name: str):
    """Task qui tourne en boucle"""
    try:
        counter = 0
        while True:
            print(f"[{name}] Running... {counter}")
            counter += 1
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        print(f"[{name}] Cancelled!")


async def main():
    print("=" * 60)
    print("Test Input Pattern")
    print("=" * 60)
    
    # Créer des tasks
    task1 = asyncio.create_task(worker("Worker1"))
    task2 = asyncio.create_task(worker("Worker2"))
    
    # Attendre un peu qu'ils démarrent
    await asyncio.sleep(0.5)
    
    # Attendre ENTRÉE dans un executor
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: input('\n✅ Bot actif ! Appuyez sur ENTRÉE pour arrêter...\n')
        )
    except (KeyboardInterrupt, EOFError):
        print("⚡ Interruption")
    finally:
        print("🛑 Arrêt des workers...")
        
        # Annuler les tasks
        task1.cancel()
        task2.cancel()
        
        # Attendre l'annulation
        await asyncio.gather(task1, task2, return_exceptions=True)
        
        print("👋 Arrêté proprement")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Au revoir !")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
