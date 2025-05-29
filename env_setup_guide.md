# 🔑 API Keys Setup - Einfache Anleitung

## ✅ EMPFOHLEN: .env Datei verwenden

Das ist viel einfacher als Windows Umgebungsvariablen!

### Schritt 1: .env Datei erstellen
```cmd
copy .env.example .env
```

### Schritt 2: .env bearbeiten
Öffne die `.env` Datei mit einem Texteditor und trage deine echten API Keys ein:

```env
# Ersetze die Platzhalter mit deinen echten Keys:
OPENAI_API_KEY=sk-proj-abcd1234...dein-echter-openai-key
CLAUDE_API_KEY=sk-ant-abcd1234...dein-echter-claude-key
ELEVENLABS_API_KEY=abcd1234...dein-echter-elevenlabs-key
```

### Schritt 3: Fertig!
Die App lädt automatisch die Keys aus der .env Datei.

## 🔗 Wo bekomme ich die API Keys?

### OpenAI (erforderlich)
1. Gehe zu: https://platform.openai.com/api-keys
2. Klicke "Create new secret key"
3. Kopiere den Key (beginnt mit `sk-proj-`)

### Claude (erforderlich)  
1. Gehe zu: https://console.anthropic.com/
2. Erstelle Account falls nötig
3. Gehe zu "API Keys" → "Create Key"
4. Kopiere den Key (beginnt mit `sk-ant-`)

### ElevenLabs (optional)
1. Gehe zu: https://elevenlabs.io/
2. Erstelle Account (kostenlose Kontingente verfügbar)
3. Gehe zu Profile → API Keys
4. Kopiere den Key

## 💡 Tipps

### .env Datei Beispiel:
```env
OPENAI_API_KEY=sk-proj-abc123...
CLAUDE_API_KEY=sk-ant-xyz789...
ELEVENLABS_API_KEY=e1a2b3c4...
```

### Wichtige Hinweise:
- ❌ **Keine Anführungszeichen** um die Keys
- ❌ **Keine Leerzeichen** vor/nach dem `=`
- ✅ **Eine Zeile pro Key**
- ✅ **Echte Keys ohne Platzhalter**

## 🚨 Sicherheit

- ✅ Die `.env` Datei bleibt lokal auf deinem Computer
- ✅ Wird nicht in Git committed (falls du das Projekt versionierst)
- ⚠️ **Teile deine API Keys niemals** mit anderen!

## 🔄 Alternative: Windows Umgebungsvariablen

Falls du lieber Umgebungsvariablen verwenden möchtest:

```cmd
setx OPENAI_API_KEY "dein_openai_key"
setx CLAUDE_API_KEY "dein_claude_key"
setx ELEVENLABS_API_KEY "dein_elevenlabs_key"
```

**Wichtig:** Nach `setx` musst du CMD neu starten!

## ✅ Testen

Nach dem Setup:
```cmd
start.bat
```

Die App sollte starten und keine API Key Fehler zeigen.
