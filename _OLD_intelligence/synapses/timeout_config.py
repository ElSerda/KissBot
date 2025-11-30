"""
⏱️ Configuration des timeouts HTTPX pour synapses neuronales

httpx.Timeout() EXIGE 4 paramètres explicitement :
- connect : Établir connexion TCP
- read    : Lire réponse (streaming LLM = LONG)
- write   : Envoyer payload JSON
- pool    : Obtenir connexion du pool

Référence: https://www.python-httpx.org/advanced/#timeout-configuration
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeoutConfig:
    """
    Configuration des timeouts HTTPX avec valeurs par défaut optimisées.
    
    frozen=True : Immutable (sécurité, pas de modification accidentelle)
    """
    connect: float = 5.0      # TCP connection (court : serveur down = rapide)
    read: float = 30.0        # LLM streaming (long : génération token-by-token)
    write: float = 10.0       # Send payload (moyen : peut être lent si gros contexte)
    pool: float = 5.0         # Connection pool (court : attente connexion libre)

    @classmethod
    def from_config(cls, config: dict) -> 'TimeoutConfig':
        """
        Crée TimeoutConfig depuis neural_llm config avec fallbacks intelligents.
        
        Args:
            config: Section neural_llm de config.yaml
            
        Returns:
            TimeoutConfig avec valeurs chargées ou defaults
            
        Example:
            >>> neural_config = {"timeout_connect": 3.0, "timeout_inference": 60.0}
            >>> timeouts = TimeoutConfig.from_config(neural_config)
            >>> timeouts.connect
            3.0
            >>> timeouts.read  # Utilise default car timeout_inference → read
            60.0
        """
        return cls(
            connect=config.get("timeout_connect", cls.connect),
            read=config.get("timeout_inference", cls.read),  # timeout_inference → read (legacy compat)
            write=config.get("timeout_write", cls.write),
            pool=config.get("timeout_pool", cls.pool)
        )

    def to_httpx_timeout(self) -> dict:
        """
        Convertit en kwargs pour httpx.Timeout().
        
        Returns:
            Dict avec les 4 paramètres requis par httpx.Timeout
            
        Example:
            >>> timeouts = TimeoutConfig(connect=5.0, read=30.0, write=10.0, pool=5.0)
            >>> timeouts.to_httpx_timeout()
            {'connect': 5.0, 'read': 30.0, 'write': 10.0, 'pool': 5.0}
        """
        return {
            "connect": self.connect,
            "read": self.read,
            "write": self.write,
            "pool": self.pool
        }
    
    def __str__(self) -> str:
        """Format lisible pour logs"""
        return f"connect={self.connect}s, read={self.read}s, write={self.write}s, pool={self.pool}s"
