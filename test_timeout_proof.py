#!/usr/bin/env python3
"""Test timeout réel - Force un blocage avec asyncio.sleep()"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
LOGGER = logging.getLogger(__name__)


async def slow_operation():
    """Simule une opération qui prend 10s"""
    LOGGER.info("🐌 Début opération lente (10s)...")
    await asyncio.sleep(10)
    LOGGER.info("✅ Opération terminée")
    return "SUCCESS"


async def test_sans_timeout():
    """Test SANS timeout - va bloquer 10s"""
    print("\n" + "=" * 70)
    print("🔴 Test 1: SANS timeout (va bloquer 10s)")
    print("=" * 70)
    
    try:
        result = await slow_operation()
        LOGGER.info(f"Résultat: {result}")
    except Exception as e:
        LOGGER.error(f"Erreur: {e}")


async def test_avec_timeout():
    """Test AVEC timeout de 2s - va timeout"""
    print("\n" + "=" * 70)
    print("🟢 Test 2: AVEC timeout de 2s (va timeout)")
    print("=" * 70)
    
    try:
        result = await asyncio.wait_for(
            slow_operation(),
            timeout=2.0
        )
        LOGGER.info(f"Résultat: {result}")
    except asyncio.TimeoutError:
        LOGGER.error("⏱️ TIMEOUT après 2s ! (opération trop lente)")
    except Exception as e:
        LOGGER.error(f"Erreur: {e}")


async def main():
    print("\n🧪 Test Timeout - asyncio.wait_for() Proof of Concept")
    print("Démonstration que le timeout fonctionne VRAIMENT\n")
    
    # Test 1: Sans timeout (bloque 10s)
    await test_sans_timeout()
    
    # Test 2: Avec timeout 2s (timeout après 2s)
    await test_avec_timeout()
    
    print("\n" + "=" * 70)
    print("✅ Tests terminés")
    print("=" * 70)
    print("📊 Conclusion:")
    print("  - Sans timeout: Opération complète en 10s")
    print("  - Avec timeout: Timeout après 2s (opération annulée)")
    print("\n✅ Le mécanisme asyncio.wait_for() fonctionne !\n")


if __name__ == "__main__":
    asyncio.run(main())
