import re
import numpy as np
from pydub import AudioSegment

# Pedalboard imports - korrigierte Import-Syntax
try:
    from pedalboard import (
        Pedalboard, 
        Reverb, 
        Delay, 
        PitchShift, 
        LowpassFilter, 
        HighpassFilter,
        Tremolo,
        Chorus,
        Flanger,
        Distortion  # Verwende Distortion statt Overdrive
    )
    PEDALBOARD_AVAILABLE = True
    print("✅ Pedalboard erfolgreich importiert")
except ImportError as e:
    print(f"❌ Pedalboard Import Fehler: {e}")
    PEDALBOARD_AVAILABLE = False

def _split_text_by_commands(text: str):
    """
    Splits the input text into segments based on DSP commands.
    Each segment is a dictionary with 'text' and 'commands'.
    Commands apply to the text segment that follows them.
    """
    command_pattern = re.compile(r"(!(?:echo|hall|pitch[+-]?|lowpass|highpass|normal|tremolo|flanger|chorus|overdrive|reverse):)")
    
    segments = []
    last_idx = 0
    
    # Find all commands and their positions
    matches = list(command_pattern.finditer(text))
    
    current_commands = []
    for match in matches:
        # Extract text before the current command
        segment_text = text[last_idx:match.start()].strip()
        
        if segment_text:
            segments.append({"text": segment_text, "commands": list(current_commands)})
            current_commands = [] # Reset commands after they've been applied to a text segment
        
        # Add the current command to the list of commands for the *next* text segment
        current_commands.append(match.group(0))
        last_idx = match.end()
        
    # Add any remaining text after the last command
    remaining_text = text[last_idx:].strip()
    if remaining_text or current_commands: # Even if no text, if there are commands, they form a segment
        segments.append({"text": remaining_text, "commands": list(current_commands)})
        
    return segments

def parse_dsp_commands(ai_response: str):
    """
    Parses DSP commands from an AI response, allowing them anywhere in the text.
    Returns a list of dictionaries, where each dictionary contains a text segment
    and a list of commands that apply to that segment.
    """
    return _split_text_by_commands(ai_response)

def clean_text_from_dsp_commands(text: str) -> str:
    """
    Removes all DSP commands from a given text string.
    """
    command_pattern = re.compile(r"(!(?:echo|hall|pitch[+-]?|lowpass|highpass|normal|tremolo|flanger|chorus|overdrive|reverse):)\s*")
    cleaned_text = command_pattern.sub("", text)
    return cleaned_text.strip()

def _apply_effects_to_segment(audio_segment: AudioSegment, commands: list) -> AudioSegment:
    """
    Applies DSP effects to a single pydub AudioSegment using pedalboard.
    """
    if not audio_segment.duration_seconds:
        return audio_segment

    if not PEDALBOARD_AVAILABLE:
        print("⚠️ Pedalboard nicht verfügbar - keine DSP-Effekte angewendet")
        return audio_segment

    sample_rate = audio_segment.frame_rate
    
    # Convert pydub AudioSegment to numpy array for processing
    # pedalboard expects float32, normalized to -1.0 to 1.0
    audio_data = np.array(audio_segment.get_array_of_samples()).astype(np.float32)
    
    # Normalize based on sample width
    if audio_segment.sample_width == 2:  # 16-bit
        audio_data = audio_data / (2**15)
    elif audio_segment.sample_width == 3:  # 24-bit
        audio_data = audio_data / (2**23)
    elif audio_segment.sample_width == 4:  # 32-bit
        audio_data = audio_data / (2**31)
    else:
        audio_data = audio_data / np.max(np.abs(audio_data))  # Fallback normalization

    # If stereo, convert to mono by taking the first channel or averaging
    if audio_segment.channels > 1:
        audio_data = audio_data.reshape(-1, audio_segment.channels)
        audio_data = np.mean(audio_data, axis=1)  # Average channels for mono

    board = Pedalboard()

    # Check for !normal: command first to reset all effects for this segment
    if any(cmd.startswith("!normal:") for cmd in commands):
        print(f"DEBUG: !normal: command detected. Skipping other DSP effects for this segment.")
        # No effects applied, return original audio
        return audio_segment
    
    # Apply effects based on commands
    effects_applied = []
    for cmd in commands:
        try:
            if cmd.startswith("!echo:"):
                # Delay effect (Echo)
                board.append(Delay(delay_seconds=0.2, feedback=0.4, mix=0.5))
                effects_applied.append("echo")
                
            elif cmd.startswith("!hall:"):
                # Reverb effect (Hall)
                board.append(Reverb(room_size=0.7, damping=0.5, wet_level=0.4, dry_level=0.6))
                effects_applied.append("hall")
                
            elif cmd.startswith("!pitch+"):
                # Extract semitones value
                semitones_str = cmd.replace("!pitch+", "").replace(":", "").strip()
                semitones = int(semitones_str) if semitones_str.isdigit() else 2
                board.append(PitchShift(semitones=semitones))
                effects_applied.append(f"pitch+{semitones}")
                
            elif cmd.startswith("!pitch-"):
                # Extract semitones value
                semitones_str = cmd.replace("!pitch-", "").replace(":", "").strip()
                semitones = int(semitones_str) if semitones_str.isdigit() else 2
                board.append(PitchShift(semitones=-semitones))
                effects_applied.append(f"pitch-{semitones}")
                
            elif cmd.startswith("!lowpass:"):
                try:
                    cutoff_str = cmd.replace("!lowpass:", "").strip()
                    cutoff = float(cutoff_str) if cutoff_str else 500.0
                    board.append(LowpassFilter(cutoff_frequency_hz=cutoff))
                    effects_applied.append(f"lowpass_{cutoff}Hz")
                except ValueError:
                    print(f"Invalid cutoff frequency for !lowpass: {cmd}. Using default 500Hz.")
                    board.append(LowpassFilter(cutoff_frequency_hz=500.0))
                    effects_applied.append("lowpass_500Hz")
                    
            elif cmd.startswith("!highpass:"):
                try:
                    cutoff_str = cmd.replace("!highpass:", "").strip()
                    cutoff = float(cutoff_str) if cutoff_str else 2000.0
                    board.append(HighpassFilter(cutoff_frequency_hz=cutoff))
                    effects_applied.append(f"highpass_{cutoff}Hz")
                except ValueError:
                    print(f"Invalid cutoff frequency for !highpass: {cmd}. Using default 2000Hz.")
                    board.append(HighpassFilter(cutoff_frequency_hz=2000.0))
                    effects_applied.append("highpass_2000Hz")
                    
            elif cmd.startswith("!tremolo:"):
                # Tremolo effect
                board.append(Tremolo(rate_hz=6.0, depth=0.5))
                effects_applied.append("tremolo")
                
            elif cmd.startswith("!flanger:"):
                # Flanger effect
                board.append(Flanger(rate_hz=0.5, depth=1.0, centre_delay_ms=7.0, feedback=0.0, mix=0.5))
                effects_applied.append("flanger")
                
            elif cmd.startswith("!chorus:"):
                # Chorus effect
                board.append(Chorus(rate_hz=1.5, depth=0.25, centre_delay_ms=7.0, feedback=0.0, mix=0.5))
                effects_applied.append("chorus")
                
            elif cmd.startswith("!overdrive:"):
                # Distortion effect (instead of Overdrive)
                board.append(Distortion(drive_db=20.0))
                effects_applied.append("overdrive")
                
            elif cmd.startswith("!reverse:"):
                # Manual reverse - flip the audio array
                audio_data = np.flip(audio_data)
                effects_applied.append("reverse")
                
            else:
                print(f"Unknown DSP command: {cmd}")
                
        except Exception as e:
            print(f"❌ Fehler beim Anwenden von Effekt '{cmd}': {e}")
            continue

    # Apply pedalboard effects if any were added
    if len(board):
        try:
            # Ensure audio_data is 2D (channels, samples) for pedalboard
            if audio_data.ndim == 1:
                audio_data = audio_data.reshape(1, -1)

            # Apply effects
            processed_audio_data = board(audio_data, sample_rate)

            # Convert back to 1D if needed
            if processed_audio_data.ndim > 1:
                processed_audio_data = processed_audio_data.flatten()

            # Convert back to original data type
            if audio_segment.sample_width == 2:  # 16-bit
                processed_audio_data = np.clip(processed_audio_data * (2**15), -(2**15), (2**15) - 1).astype(np.int16)
            elif audio_segment.sample_width == 3:  # 24-bit  
                processed_audio_data = np.clip(processed_audio_data * (2**23), -(2**23), (2**23) - 1).astype(np.int32)
            elif audio_segment.sample_width == 4:  # 32-bit
                processed_audio_data = np.clip(processed_audio_data * (2**31), -(2**31), (2**31) - 1).astype(np.int32)

            # Create new AudioSegment
            result_segment = AudioSegment(
                processed_audio_data.tobytes(),
                frame_rate=sample_rate,
                sample_width=audio_segment.sample_width,
                channels=1  # Mono after processing
            )
            
            print(f"✅ DSP-Effekte angewendet: {', '.join(effects_applied)}")
            return result_segment

        except Exception as e:
            print(f"❌ Fehler beim Anwenden der Pedalboard-Effekte: {e}")
            return audio_segment
    else:
        # No pedalboard effects, but might have manual effects like reverse
        if "reverse" in effects_applied:
            # Convert back to AudioSegment for reverse effect
            if audio_segment.sample_width == 2:
                processed_audio_data = np.clip(audio_data * (2**15), -(2**15), (2**15) - 1).astype(np.int16)
            else:
                processed_audio_data = (audio_data * (2**(8 * audio_segment.sample_width - 1))).astype(np.int16)
                
            result_segment = AudioSegment(
                processed_audio_data.tobytes(),
                frame_rate=sample_rate,
                sample_width=audio_segment.sample_width,
                channels=1
            )
            print(f"✅ Manueller Effekt angewendet: reverse")
            return result_segment

    return audio_segment