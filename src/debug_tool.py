"""
Debug Tool für Voice Chat App
Testet alle APIs einzeln um Probleme zu identifizieren
"""

import os
import requests
import openai

# .env laden falls vorhanden
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ .env Datei geladen")
except ImportError:
    print("⚠️ python-dotenv nicht installiert")

# API Keys laden
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

def test_internet():
    """Testet grundlegende Internetverbindung"""
    print("\n🌐 Teste Internetverbindung...")
    try:
        response = requests.get("https://httpbin.org/status/200", timeout=10)
        if response.status_code == 200:
            print("✅ Internet funktioniert")
            return True
        else:
            print(f"❌ Unerwarteter Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Internetverbindung fehlgeschlagen: {e}")
        return False

def test_openai_api():
    """Testet OpenAI Whisper API"""
    print("\n🤖 Teste OpenAI API...")
    
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY nicht gesetzt")
        return False
    
    if not OPENAI_API_KEY.startswith("sk-"):
        print("❌ OPENAI_API_KEY hat falsches Format (sollte mit 'sk-' beginnen)")
        return False
    
    print(f"🔑 API Key: {OPENAI_API_KEY[:10]}...{OPENAI_API_KEY[-4:]}")
    
    try:
        openai.api_key = OPENAI_API_KEY
        
        # Teste mit einfacher API-Anfrage
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Teste zuerst die Models Endpoint (einfacher)
        models = client.models.list()
        print("✅ OpenAI API Connection OK")
        
        # Optional: Teste Whisper mit einer kleinen Dummy-Datei
        print("⚠️ Whisper Test übersprungen (braucht Audio-Datei)")
        return True
        
    except Exception as e:
        error_str = str(e)
        if "529" in error_str:
            print("❌ OpenAI Server überlastet (529) - versuche es später nochmal")
        elif "401" in error_str:
            print("❌ OpenAI API Key ungültig")
        elif "429" in error_str:
            print("❌ OpenAI Rate Limit erreicht")
        elif "timeout" in error_str.lower():
            print("❌ OpenAI API Timeout")
        else:
            print(f"❌ OpenAI API Fehler: {e}")
        return False

def test_claude_api():
    """Testet Claude API"""
    print("\n🎭 Teste Claude API...")
    
    if not CLAUDE_API_KEY:
        print("❌ CLAUDE_API_KEY nicht gesetzt")
        return False
    
    if not CLAUDE_API_KEY.startswith("sk-ant-"):
        print("❌ CLAUDE_API_KEY hat falsches Format (sollte mit 'sk-ant-' beginnen)")
        return False
    
    print(f"🔑 API Key: {CLAUDE_API_KEY[:15]}...{CLAUDE_API_KEY[-4:]}")
    
    try:
        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 50,
            "messages": [{"role": "user", "content": "Sage nur 'Test erfolgreich'"}]
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages", 
            headers=headers, 
            json=data, 
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result["content"][0]["text"]
            print(f"✅ Claude API funktioniert: '{answer}'")
            return True
        elif response.status_code == 529:
            print("❌ Claude Server überlastet (529) - warte 1-2 Minuten und versuche nochmal")
        elif response.status_code == 401:
            print("❌ Claude API Key ungültig")
        elif response.status_code == 429:
            print("❌ Claude Rate Limit erreicht")
        else:
            print(f"❌ Claude API Fehler {response.status_code}: {response.text[:200]}")
        
        return False
        
    except requests.exceptions.Timeout:
        print("❌ Claude API Timeout")
        return False
    except Exception as e:
        print(f"❌ Claude API Fehler: {e}")
        return False

def test_elevenlabs_api():
    """Testet ElevenLabs API"""
    print("\n🔊 Teste ElevenLabs API...")
    
    if not ELEVENLABS_API_KEY:
        print("⚠️ ELEVENLABS_API_KEY nicht gesetzt (optional)")
        return None
    
    print(f"🔑 API Key: {ELEVENLABS_API_KEY[:10]}...{ELEVENLABS_API_KEY[-4:]}")
    
    try:
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        # Teste zuerst die User Info (einfacher)
        response = requests.get(
            "https://api.elevenlabs.io/v1/user", 
            headers=headers, 
            timeout=15
        )
        
        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ ElevenLabs API funktioniert")
            return True
        elif response.status_code == 529:
            print("❌ ElevenLabs Server überlastet (529)")
        elif response.status_code == 401:
            print("❌ ElevenLabs API Key ungültig")
        else:
            print(f"❌ ElevenLabs API Fehler {response.status_code}")
        
        return False
        
    except Exception as e:
        print(f"❌ ElevenLabs API Fehler: {e}")
        return False

def check_api_status():
    """Prüft API Status Seiten"""
    print("\n📊 Prüfe API Status...")
    
    status_urls = {
        "OpenAI": "https://status.openai.com/api/v2/summary.json",
        "Claude": "https://status.anthropic.com/api/v2/summary.json", 
        "ElevenLabs": "https://status.elevenlabs.io/api/v2/summary.json"
    }
    
    for service, url in status_urls.items():
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", {}).get("description", "unknown")
                print(f"📊 {service}: {status}")
            else:
                print(f"⚠️ {service}: Status nicht verfügbar")
        except:
            print(f"⚠️ {service}: Status-Check fehlgeschlagen")

def main():
    print("🔧 Voice Chat App - API Debug Tool")
    print("=" * 50)
    
    # Teste alle APIs
    internet_ok = test_internet()
    
    if internet_ok:
        check_api_status()
        
        openai_ok = test_openai_api()
        claude_ok = test_claude_api()
        elevenlabs_ok = test_elevenlabs_api()
        
        print("\n" + "=" * 50)
        print("📋 ZUSAMMENFASSUNG:")
        print(f"🌐 Internet: {'✅ OK' if internet_ok else '❌ FEHLER'}")
        print(f"🤖 OpenAI: {'✅ OK' if openai_ok else '❌ FEHLER'}")
        print(f"🎭 Claude: {'✅ OK' if claude_ok else '❌ FEHLER'}")
        
        if elevenlabs_ok is None:
            print("🔊 ElevenLabs: ⚠️ Nicht konfiguriert")
        else:
            print(f"🔊 ElevenLabs: {'✅ OK' if elevenlabs_ok else '❌ FEHLER'}")
        
        if openai_ok and claude_ok:
            print("\n🎉 Alle wichtigen APIs funktionieren!")
            print("Du kannst die Voice Chat App starten.")
        else:
            print("\n⚠️ Einige APIs haben Probleme.")
            print("Prüfe die Fehlermeldungen oben und:")
            print("- Warte 1-2 Minuten bei 529 Fehlern")
            print("- Prüfe API Keys bei 401 Fehlern")
            print("- Prüfe API Status bei anhaltenden Problemen")
    
    print("\n🔗 Hilfreiche Links:")
    print("- OpenAI Status: https://status.openai.com/")
    print("- Claude Status: https://status.anthropic.com/")
    print("- ElevenLabs Status: https://status.elevenlabs.io/")
    
    input("\nDrücke Enter zum Beenden...")

if __name__ == "__main__":
    main()
