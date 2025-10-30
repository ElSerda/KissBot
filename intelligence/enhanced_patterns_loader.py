#!/usr/bin/env python3
"""
🎯 Enhanced Patterns Loader for StaticQuantumClassifier V3.0
Chargeur de patterns avancés avec support YAML et contexte gaming
"""

import yaml
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path


class EnhancedPatternsLoader:
    """
    🎯 Chargeur de patterns avancés avec contexte gaming

    Fonctionnalités:
    - Chargement patterns YAML avec weights
    - Context modifiers dynamiques
    - Support gaming-specific patterns
    - Fallback vers patterns par défaut
    """

    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)

        # Path du fichier de configuration
        if config_path is None:
            # Chemin par défaut relatif au projet
            self.config_path = Path(__file__).parent.parent / "config" / "enhanced_patterns.yaml"
        else:
            self.config_path = Path(config_path)

        # Configuration chargée
        self.patterns_config: Dict[str, Any] = {}
        self.classification_rules: Dict[str, Dict] = {}
        self.context_modifiers: Dict[str, float] = {}
        self.weights_config: Dict[str, float] = {}

        # Chargement initial
        self.load_patterns()

    def load_patterns(self) -> bool:
        """🔄 Charge les patterns depuis le fichier YAML"""
        try:
            if not self.config_path.exists():
                self.logger.warning(f"📄 Fichier patterns non trouvé: {self.config_path}")
                self._load_default_patterns()
                return False

            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.patterns_config = yaml.safe_load(file)

            # Extraction des sections
            self._extract_classification_rules()
            self._extract_context_modifiers()
            self._extract_weights_config()

            self.logger.info(f"✅ Patterns chargés depuis {self.config_path}")
            self.logger.debug(f"📊 Classes: {list(self.classification_rules.keys())}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur chargement patterns: {e}")
            self._load_default_patterns()
            return False

    def _extract_classification_rules(self):
        """📋 Extrait les règles de classification avec compatibilité ImprovedClassifier"""
        self.classification_rules = {}

        # Note: Mapping weight vers priority (pour référence future)
        # 1.0 -> instant_response (ping)
        # 0.8 -> question_simple (gen_short)
        # 0.9 -> factual (lookup)
        # 1.1 -> complex_analysis (gen_long)

        for class_name in ['ping', 'gen_short', 'lookup', 'gen_long']:
            if class_name in self.patterns_config:
                class_config = self.patterns_config[class_name]
                weight = class_config.get('weight', 1.0)

                # Mapping intelligent weight → priority
                if weight >= 1.1:
                    priority = "complex_analysis"
                elif weight >= 1.0:
                    priority = "instant_response"
                elif weight >= 0.9:
                    priority = "factual"
                else:
                    priority = "question_simple"

                self.classification_rules[class_name] = {
                    'patterns': class_config.get('patterns', []),
                    'priority': priority,  # Compatible ImprovedClassifier
                    'weight': weight,      # Garde weight original
                    'context_modifiers': class_config.get('context_modifiers', {})
                }

    def _extract_context_modifiers(self):
        """🎛️ Extrait les modificateurs de contexte globaux"""
        global_mods = self.patterns_config.get('global_modifiers', {})
        self.context_modifiers = global_mods

    def _extract_weights_config(self):
        """⚖️ Extrait la configuration des poids"""
        self.weights_config = self.patterns_config.get('classification_weights', {
            'pattern_match': 0.6,
            'length_analysis': 0.2,
            'complexity_analysis': 0.1,
            'context_bonus': 0.1
        })

    def _load_default_patterns(self):
        """🔄 Charge les patterns par défaut en cas d'échec"""
        self.logger.info("📄 Chargement patterns par défaut")

        self.classification_rules = {
            "ping": {
                "patterns": ["!", "!uptime", "!ping", "!game", "!help", "gg", "wp", "kekw"],
                "weight": 1.0,
                "context_modifiers": {}
            },
            "gen_short": {
                "patterns": ["salut", "hello", "comment ça va", "merci", "lol", "nice"],
                "weight": 0.8,
                "context_modifiers": {}
            },
            "lookup": {
                "patterns": ["c'est quoi", "qu'est-ce que", "stats", "build", "guide"],
                "weight": 0.9,
                "context_modifiers": {}
            },
            "gen_long": {
                "patterns": ["explique", "comment faire", "aide moi", "stratégie"],
                "weight": 1.1,
                "context_modifiers": {}
            }
        }

        self.context_modifiers = {
            'very_short': 0.8, 'short': 0.9, 'medium': 1.0,
            'long': 1.1, 'very_long': 1.2
        }

        self.weights_config = {
            'pattern_match': 0.6, 'length_analysis': 0.2,
            'complexity_analysis': 0.1, 'context_bonus': 0.1
        }

    def get_classification_rules(self) -> Dict[str, Dict]:
        """📋 Retourne les règles de classification"""
        return self.classification_rules

    def get_context_modifiers(self) -> Dict[str, float]:
        """🎛️ Retourne les modificateurs de contexte"""
        return self.context_modifiers

    def get_weights_config(self) -> Dict[str, float]:
        """⚖️ Retourne la configuration des poids"""
        return self.weights_config

    def get_pattern_weight(self, class_name: str) -> float:
        """🎯 Retourne le poids d'une classe spécifique"""
        return self.classification_rules.get(class_name, {}).get('weight', 1.0)

    def get_gaming_context_boost(self, stimulus: str, game_type: Optional[str] = None) -> float:
        """🎮 Calcule le boost contextuel gaming"""
        if not game_type:
            return 1.0

        gaming_contexts = self.patterns_config.get('gaming_contexts', {})
        if game_type not in gaming_contexts:
            return 1.0

        context_config = gaming_contexts[game_type]
        boost_patterns = context_config.get('boost_patterns', [])
        boost_weight = context_config.get('boost_weight', 1.0)

        stimulus_lower = stimulus.lower()
        for pattern in boost_patterns:
            if pattern in stimulus_lower:
                return boost_weight

        return 1.0

    def reload_patterns(self) -> bool:
        """🔄 Recharge les patterns depuis le fichier"""
        self.logger.info("🔄 Rechargement patterns...")
        return self.load_patterns()

    def get_pattern_stats(self) -> Dict[str, Any]:
        """📊 Retourne les statistiques des patterns chargés"""
        stats: Dict[str, Any] = {
            'total_classes': len(self.classification_rules),
            'total_patterns': 0,
            'classes': {}
        }

        for class_name, rules in self.classification_rules.items():
            patterns = rules.get('patterns', [])
            pattern_count = len(patterns) if isinstance(patterns, list) else 0
            total_patt = stats['total_patterns']
            stats['total_patterns'] = int(total_patt) + pattern_count if isinstance(total_patt, int) else pattern_count
            
            context_mods = rules.get('context_modifiers', {})
            context_mods_len = len(context_mods) if isinstance(context_mods, dict) else 0
            
            stats['classes'][class_name] = {
                'pattern_count': pattern_count,
                'weight': rules.get('weight', 1.0),
                'context_modifiers': context_mods_len
            }

        return stats

    def validate_patterns(self) -> List[str]:
        """✅ Valide la configuration des patterns"""
        issues = []

        # Vérification classes obligatoires
        required_classes = ['ping', 'gen_short', 'lookup', 'gen_long']
        for class_name in required_classes:
            if class_name not in self.classification_rules:
                issues.append(f"Classe manquante: {class_name}")
            elif not self.classification_rules[class_name].get('patterns'):
                issues.append(f"Patterns vides pour classe: {class_name}")

        # Vérification poids valides
        for class_name, rules in self.classification_rules.items():
            weight = rules.get('weight', 1.0)
            if not isinstance(weight, (int, float)) or weight <= 0:
                issues.append(f"Poids invalide pour {class_name}: {weight}")

        return issues


# 🧪 Test et démonstration
def demo_enhanced_patterns():
    """🧪 Démonstration du chargeur de patterns"""
    print("🎯 === DEMO ENHANCED PATTERNS LOADER ===")

    loader = EnhancedPatternsLoader()

    # Stats de chargement
    stats = loader.get_pattern_stats()
    print(f"📊 Patterns chargés: {stats['total_patterns']} dans {stats['total_classes']} classes")

    for class_name, class_stats in stats['classes'].items():
        print(f"  {class_name}: {class_stats['pattern_count']} patterns (poids: {class_stats['weight']})")

    # Test patterns spécifiques
    print("\n🔍 Tests patterns:")
    test_rules = loader.get_classification_rules()

    for class_name, rules in test_rules.items():
        example_patterns = rules['patterns'][:3]  # Premiers 3 patterns
        print(f"  {class_name}: {example_patterns}")

    # Validation
    issues = loader.validate_patterns()
    if issues:
        print(f"\n⚠️ Issues trouvées: {issues}")
    else:
        print("\n✅ Configuration patterns valide !")


if __name__ == "__main__":
    demo_enhanced_patterns()
