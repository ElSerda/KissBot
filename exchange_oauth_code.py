"""
🔐 Script pour échanger un code OAuth contre des tokens
Usage: python exchange_oauth_code.py <code>
"""
import sys
import requests
import yaml

def exchange_code_for_token(code: str, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:3000"):
    """
    Échange un code OAuth contre un access_token et refresh_token
    """
    url = "https://id.twitch.tv/oauth2/token"
    
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    
    print("🔄 Échange du code OAuth...")
    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        return token_data
    else:
        print(f"❌ Erreur: {response.status_code}")
        print(response.text)
        return None


def validate_token(access_token: str):
    """
    Valide le token et récupère les infos utilisateur
    """
    url = "https://id.twitch.tv/oauth2/validate"
    headers = {"Authorization": f"OAuth {access_token}"}
    
    print("🔍 Validation du token...")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Erreur validation: {response.status_code}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python exchange_oauth_code.py <code>")
        print("\nExemple:")
        print("  python exchange_oauth_code.py b22gt0rtw7ftyyxg1y40y365vtmqte")
        sys.exit(1)
    
    code = sys.argv[1]
    
    # Charger la config pour récupérer client_id et client_secret
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    client_id = config["twitch"]["client_id"]
    client_secret = config["twitch"]["client_secret"]
    
    print("=" * 70)
    print("🔐 Échange du code OAuth contre des tokens")
    print("=" * 70)
    print(f"Code: {code[:20]}...")
    print()
    
    # Échanger le code
    token_data = exchange_code_for_token(code, client_id, client_secret)
    
    if not token_data:
        print("❌ Échec de l'échange du code")
        sys.exit(1)
    
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_in = token_data.get("expires_in", 0)
    
    print("✅ Tokens obtenus!")
    print()
    
    # Valider et récupérer les infos
    validation = validate_token(access_token)
    
    if validation:
        user_id = validation["user_id"]
        login = validation["login"]
        scopes = validation.get("scopes", [])
        
        print(f"👤 Utilisateur: {login} (ID: {user_id})")
        print(f"⏱️  Expire dans: {expires_in} secondes (~{expires_in//3600}h)")
        print(f"🔑 Scopes ({len(scopes)}):")
        for scope in sorted(scopes):
            print(f"   ✓ {scope}")
        print()
        print("=" * 70)
        print("📋 TOKENS À COPIER DANS config/config.yaml")
        print("=" * 70)
        print()
        print(f"Pour le compte: {login}")
        print()
        print(f"  {login}:")
        print(f"    user_id: '{user_id}'")
        print(f"    access_token: {access_token}")
        print(f"    refresh_token: {refresh_token}")
        print()
        print("=" * 70)
        print()
        print("💡 Copie ce bloc dans config/config.yaml sous twitch.tokens")
        print("   N'oublie pas de mettre à jour bot_id si c'est le bot!")
        print()
    else:
        print("⚠️  Impossible de valider le token")
        print()
        print("Tokens bruts:")
        print(f"  access_token: {access_token}")
        print(f"  refresh_token: {refresh_token}")


if __name__ == "__main__":
    main()
