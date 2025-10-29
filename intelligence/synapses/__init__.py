"""
🧠 Neural Synapses - KissBot Brain Components
"""

# Imports absolus pour Pylance
try:
    from intelligence.synapses.cloud_synapse import CloudSynapse
    from intelligence.synapses.local_synapse import LocalSynapse

    __all__ = ["LocalSynapse", "CloudSynapse"]
except ImportError:
    # Fallback pour tests
    __all__ = []
