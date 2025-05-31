#!/usr/bin/env python3
"""
DSP Test Script - Testet alle Audio-Effekte einzeln
"""
import os
import sys
import time
from pydub import AudioSegment
from pydub.generators import Sine

# Füge src-Verzeichnis zum Pfad hinzu
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.dsp_processor import _apply_effects_to_segment, parse_dsp_commands, clean_text_from_dsp_commands
    print("✅ DSP Processor erfolgreich importiert")
except ImportError as e:
    print(f"❌ Import Fehler: {e}")
    sys.exit(1)

def create_test_audio():
    """Erstellt ein Test-Audio-Signal (1-Sekunden-Sinus-Ton)"""
    # Generiere einen 440Hz Sinus-Ton für 1 Sekunde
    tone = Sine(440).to_audio_segment(duration=1000)  # 1000ms = 1 Sekunde
    return tone

def test_single_effect(effect_command, test_audio):
    """Testet einen einzelnen DSP-Effekt"""
    print(f"\n🧪 Teste Effekt: {effect_command}")
    
    try:
        # Test-Audio mit Effekt verarbeiten
        processed_audio = _apply_effects_to_segment(test_audio, [effect_command])
        
        # Überprüfe ob sich etwas geändert hat
        if processed_audio != test_audio:
            print(f"✅ Effekt '{effect_command}' erfolgreich angewendet")
            
            # Speichere Test-Datei
            output_dir = "dsp_test_output"
            os.makedirs(output_dir, exist_ok=True)
            
            # Bereinige Effekt-Namen für Dateinamen
            safe_name = effect_command.replace(":", "").replace("+", "plus").replace("-", "minus")
            output_file = os.path.join(output_dir, f"test_{safe_name}.wav")
            
            processed_audio.export(output_file, format="wav")
            print(f"📁 Test-Datei gespeichert: {output_file}")
            
            return True
        else:
            print(f"⚠️ Effekt '{effect_command}' hat keine Änderung bewirkt")
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim Testen von '{effect_command}': {e}")
        return False

def test_text_parsing():
    """Testet das Parsing von DSP-Befehlen aus Text"""
    print("\n📝 Teste Text-Parsing...")
    
    test_texts = [
        "!hall: Dies ist ein Test mit Hall-Effekt.",
        "!echo: !pitch+2: Kombinierte Effekte im Text.",
        "Normaler Text ohne Effekte.",
        "!tremolo: Vibrierende Stimme !normal: und dann wieder normal.",
        "!flanger: !chorus: !overdrive: Viele Effekte auf einmal!"
    ]
    
    for text in test_texts:
        print(f"\nInput: '{text}'")
        
        # Parse DSP Befehle
        segments = parse_dsp_commands(text)
        print(f"Segments: {segments}")
        
        # Bereinige Text
        cleaned = clean_text_from_dsp_commands(text)
        print(f"Cleaned: '{cleaned}'")

def test_all_effects():
    """Testet alle verfügbaren DSP-Effekte"""
    print("🎛️ DSP-Effekte Testscript")
    print("=" * 50)
    
    # Teste Text-Parsing zuerst
    test_text_parsing()
    
    # Erstelle Test-Audio
    print("\n🎵 Erstelle Test-Audio (440Hz Sinus-Ton, 1 Sekunde)...")
    test_audio = create_test_audio()
    
    # Liste aller zu testenden Effekte
    effects_to_test = [
        "!echo:",
        "!hall:",
        "!pitch+2:",
        "!pitch-2:",
        "!pitch+5:",
        "!pitch-5:",
        "!lowpass:500:",
        "!lowpass:1000:",
        "!highpass:2000:",
        "!highpass:1000:",
        "!tremolo:",
        "!flanger:",
        "!chorus:",
        "!overdrive:",
        "!reverse:",
        "!normal:"
    ]
    
    # Teste jeden Effekt einzeln
    successful_effects = []
    failed_effects = []
    
    for effect in effects_to_test:
        if test_single_effect(effect, test_audio):
            successful_effects.append(effect)
        else:
            failed_effects.append(effect)
        
        # Kleine Pause zwischen Tests
        time.sleep(0.1)
    
    # Teste Effekt-Kombinationen
    print("\n🔗 Teste Effekt-Kombinationen...")
    
    combinations = [
        ["!hall:", "!echo:"],
        ["!pitch+2:", "!tremolo:"],
        ["!chorus:", "!reverb:"],
        ["!lowpass:800:", "!overdrive:"]
    ]
    
    for combo in combinations:
        print(f"\n🧪 Teste Kombination: {combo}")
        try:
            processed = _apply_effects_to_segment(test_audio, combo)
            print(f"✅ Kombination erfolgreich: {combo}")
        except Exception as e:
            print(f"❌ Kombination fehlgeschlagen: {combo} - {e}")
    
    # Zusammenfassung
    print("\n" + "=" * 50)
    print("📊 TEST-ZUSAMMENFASSUNG")
    print("=" * 50)
    
    print(f"✅ Erfolgreiche Effekte ({len(successful_effects)}):")
    for effect in successful_effects:
        print(f"   - {effect}")
    
    if failed_effects:
        print(f"\n❌ Fehlgeschlagene Effekte ({len(failed_effects)}):")
        for effect in failed_effects:
            print(f"   - {effect}")
    
    success_rate = len(successful_effects) / len(effects_to_test) * 100
    print(f"\n📈 Erfolgsrate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 DSP-System ist bereit für den Einsatz!")
    elif success_rate >= 50:
        print("⚠️ DSP-System funktioniert teilweise - einige Effekte haben Probleme")
    else:
        print("❌ DSP-System hat schwerwiegende Probleme")
    
    print("\n💡 Tipps:")
    print("- Teste die generierten Audio-Dateien im 'dsp_test_output' Ordner")
    print("- Bei Problemen: überprüfe ob 'pedalboard' korrekt installiert ist")
    print("- Führe 'pip install pedalboard' aus, falls Importfehler auftreten")

if __name__ == "__main__":
    test_all_effects()