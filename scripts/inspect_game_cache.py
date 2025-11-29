#!/usr/bin/env python3
"""
Script interactif pour inspecter le cache intelligent de jeux

Usage:
    python scripts/inspect_game_cache.py [--db kissbot.db]
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.manager import DatabaseManager


def format_timestamp(ts: int) -> str:
    """Format UNIX timestamp en date lisible."""
    if not ts:
        return "N/A"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def display_stats(db: DatabaseManager):
    """Affiche les statistiques globales du cache."""
    stats = db.get_cache_stats()
    
    print("\n" + "="*80)
    print("📊 STATISTIQUES GLOBALES DU CACHE")
    print("="*80)
    
    if stats['total_entries'] == 0:
        print("⚠️  Cache vide - aucune entrée trouvée")
        return
    
    print(f"\n  Total d'entrées:        {stats['total_entries']}")
    print(f"  Total de hits:          {stats['total_hits']}")
    print(f"  Confiance moyenne:      {stats['avg_confidence']:.2%}")
    print(f"\n  Haute qualité (≥95%):   {stats['high_quality']} ({stats['high_quality']/stats['total_entries']*100:.1f}%)")
    print(f"  Basse qualité (<90%):   {stats['low_quality']} ({stats['low_quality']/stats['total_entries']*100:.1f}%)")
    print(f"  Résultats ambigus:      {stats['ambiguous']}")
    print(f"  Avec lien canonique:    {stats['has_canonical']}")


def display_top_games(db: DatabaseManager, limit: int = 10):
    """Affiche les jeux les plus recherchés."""
    print("\n" + "="*80)
    print(f"🏆 TOP {limit} JEUX LES PLUS RECHERCHÉS")
    print("="*80)
    
    games = db.get_top_games(limit)
    
    if not games:
        print("⚠️  Aucun jeu dans le cache")
        return
    
    print(f"\n  {'#':<4} {'Query':<35} {'Hits':<6} {'Confidence':<12} {'Type':<20}")
    print("  " + "-"*76)
    
    for i, game in enumerate(games, 1):
        query = game['query']
        if len(query) > 33:
            query = query[:30] + "..."
        
        confidence_bar = "█" * int(game['confidence'] * 10)
        confidence_str = f"{game['confidence']:.2%} {confidence_bar}"
        
        print(f"  {i:<4} {query:<35} {game['hit_count']:<6} {confidence_str:<12} {game['result_type']:<20}")


def search_game_in_cache(db: DatabaseManager, query: str):
    """Recherche un jeu spécifique dans le cache."""
    print("\n" + "="*80)
    print(f"🔍 RECHERCHE: '{query}'")
    print("="*80)
    
    cached = db.get_cached_game(query)
    
    if not cached:
        print(f"\n❌ Aucun résultat trouvé pour '{query}'")
        
        # Suggérer des résultats similaires
        import sqlite3
        with db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT query, confidence FROM game_cache WHERE query LIKE ? LIMIT 5",
                (f"%{query.lower()}%",)
            )
            similar = cursor.fetchall()
            
            if similar:
                print("\n💡 Résultats similaires:")
                for row in similar:
                    print(f"   • {row[0]} (confidence: {row[1]:.2%})")
        return
    
    print(f"\n✅ Résultat trouvé!")
    print(f"\n  Query:              {cached['query']}")
    print(f"  Confidence:         {cached['confidence']:.2%} {'█' * int(cached['confidence'] * 10)}")
    print(f"  Type:               {cached['result_type']}")
    print(f"  Hit count:          {cached['hit_count']}")
    print(f"  Last hit:           {format_timestamp(cached['last_hit'])}")
    print(f"  Cached at:          {format_timestamp(cached['cached_at'])}")
    
    if cached.get('canonical_query'):
        print(f"  Canonical query:    {cached['canonical_query']}")
    
    # Afficher les données du jeu
    game_data = cached['game_data']
    print(f"\n  🎮 Jeu:")
    print(f"     Nom:             {game_data.get('name', 'N/A')}")
    print(f"     Année:           {game_data.get('year', 'N/A')}")
    
    if game_data.get('rating_rawg'):
        print(f"     Rating RAWG:     {game_data['rating_rawg']:.1f}/5.0")
    
    if game_data.get('genres'):
        print(f"     Genres:          {', '.join(game_data['genres'][:3])}")
    
    if game_data.get('platforms'):
        print(f"     Plateformes:     {', '.join(game_data['platforms'][:5])}")
    
    # Afficher les alternatives si présentes
    if cached.get('alternatives'):
        print(f"\n  🔀 Alternatives ({len(cached['alternatives'])}):")
        for i, alt in enumerate(cached['alternatives'][:3], 1):
            print(f"     {i}. {alt.get('name', 'N/A')} ({alt.get('year', '?')})")


def display_quality_breakdown(db: DatabaseManager):
    """Affiche la répartition des entrées par qualité."""
    print("\n" + "="*80)
    print("📈 RÉPARTITION PAR QUALITÉ")
    print("="*80)
    
    import sqlite3
    with db._get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                CASE 
                    WHEN confidence >= 0.95 THEN 'Excellent (≥95%)'
                    WHEN confidence >= 0.90 THEN 'Bon (90-95%)'
                    WHEN confidence >= 0.85 THEN 'Moyen (85-90%)'
                    ELSE 'Faible (<85%)'
                END as quality,
                COUNT(*) as count,
                AVG(hit_count) as avg_hits
            FROM game_cache
            GROUP BY quality
            ORDER BY MIN(confidence) DESC
        """)
        
        results = cursor.fetchall()
        
        if not results:
            print("\n⚠️  Aucune donnée")
            return
        
        print(f"\n  {'Qualité':<20} {'Entrées':<10} {'Avg Hits':<10} {'Graph':<30}")
        print("  " + "-"*70)
        
        total = sum(row[1] for row in results)
        
        for row in results:
            quality, count, avg_hits = row
            percentage = count / total * 100
            bar = "█" * int(percentage / 2)  # Max 50 chars
            print(f"  {quality:<20} {count:<10} {avg_hits or 0:<10.1f} {bar} {percentage:.1f}%")


def display_recent_additions(db: DatabaseManager, limit: int = 5):
    """Affiche les ajouts récents au cache."""
    print("\n" + "="*80)
    print(f"🆕 {limit} DERNIERS AJOUTS AU CACHE")
    print("="*80)
    
    import sqlite3
    with db._get_connection() as conn:
        cursor = conn.execute("""
            SELECT query, confidence, result_type, cached_at, hit_count
            FROM game_cache
            ORDER BY cached_at DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        
        if not results:
            print("\n⚠️  Aucune entrée")
            return
        
        print(f"\n  {'Query':<35} {'Confidence':<12} {'Type':<15} {'Cached':<20}")
        print("  " + "-"*82)
        
        for row in results:
            query, confidence, result_type, cached_at, hit_count = row
            if len(query) > 33:
                query = query[:30] + "..."
            
            cached_time = format_timestamp(cached_at)
            confidence_str = f"{confidence:.2%}"
            
            print(f"  {query:<35} {confidence_str:<12} {result_type:<15} {cached_time:<20}")


def interactive_menu(db: DatabaseManager):
    """Menu interactif."""
    while True:
        print("\n" + "="*80)
        print("🎮 INSPECTEUR DE CACHE INTELLIGENT")
        print("="*80)
        print("\n  1. 📊 Statistiques globales")
        print("  2. 🏆 Top jeux (les plus recherchés)")
        print("  3. 🔍 Rechercher un jeu spécifique")
        print("  4. 📈 Répartition par qualité")
        print("  5. 🆕 Derniers ajouts")
        print("  6. 🧹 Nettoyer le cache (peu utilisé)")
        print("  0. ❌ Quitter")
        
        choice = input("\n➜ Votre choix: ").strip()
        
        if choice == "1":
            display_stats(db)
        elif choice == "2":
            try:
                limit = int(input("  Nombre de jeux à afficher [10]: ") or "10")
            except ValueError:
                limit = 10
            display_top_games(db, limit)
        elif choice == "3":
            query = input("  Query à rechercher: ").strip()
            if query:
                search_game_in_cache(db, query)
        elif choice == "4":
            display_quality_breakdown(db)
        elif choice == "5":
            try:
                limit = int(input("  Nombre d'entrées [5]: ") or "5")
            except ValueError:
                limit = 5
            display_recent_additions(db, limit)
        elif choice == "6":
            min_hits = int(input("  Nombre minimum de hits [5]: ") or "5")
            days = int(input("  Âge maximum en jours [30]: ") or "30")
            print(f"\n  ⚠️  Cela va supprimer les entrées avec < {min_hits} hits ET > {days} jours")
            confirm = input("  Confirmer? (y/N): ").strip().lower()
            if confirm == 'y':
                deleted = db.cleanup_old_cache(min_hits, days)
                print(f"\n  ✅ {deleted} entrée(s) supprimée(s)")
            else:
                print("  ❌ Annulé")
        elif choice == "0":
            print("\n👋 Au revoir!")
            break
        else:
            print("\n❌ Choix invalide")
        
        input("\nAppuyez sur Entrée pour continuer...")


def main():
    parser = argparse.ArgumentParser(
        description="Inspecteur de cache intelligent pour KissBot"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="kissbot.db",
        help="Chemin vers la base de données (défaut: kissbot.db)"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Afficher seulement les statistiques et quitter"
    )
    parser.add_argument(
        "--top",
        type=int,
        metavar="N",
        help="Afficher les N jeux les plus recherchés et quitter"
    )
    parser.add_argument(
        "--search",
        type=str,
        metavar="QUERY",
        help="Rechercher un jeu spécifique et quitter"
    )
    
    args = parser.parse_args()
    
    # Vérifier que la DB existe
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ Database not found: {args.db}")
        print(f"   Searched at: {db_path.absolute()}")
        sys.exit(1)
    
    print(f"📦 Loading database: {args.db}")
    db = DatabaseManager(db_path=str(db_path))
    print("✅ Database loaded!")
    
    # Mode non-interactif
    if args.stats:
        display_stats(db)
        sys.exit(0)
    
    if args.top:
        display_top_games(db, args.top)
        sys.exit(0)
    
    if args.search:
        search_game_in_cache(db, args.search)
        sys.exit(0)
    
    # Mode interactif
    try:
        interactive_menu(db)
    except KeyboardInterrupt:
        print("\n\n👋 Au revoir!")
        sys.exit(0)


if __name__ == "__main__":
    main()
