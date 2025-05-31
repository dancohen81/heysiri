import re
import numpy as np
from pydub import AudioSegment
from pedalboard import Pedalboard, Reverb, Delay, PitchShift, LowpassFilter, HighpassFilter
# from pedalboard.plugins import Tremolo, Chorus, Flanger, Overdrive # Commented out due to persistent import issues
from pedalboard.io import AudioFile

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

    sample_rate = audio_segment.frame_rate
    
    # Convert pydub AudioSegment to numpy array for processing
    # pedalboard expects float32, normalized to -1.0 to 1.0
    audio_data = np.array(audio_segment.get_array_of_samples()).astype(np.float32) / (2**15) # Assuming 16-bit audio

    # If stereo, convert to mono by taking the first channel or averaging
    if audio_segment.channels > 1:
        audio_data = audio_data.reshape(-1, audio_segment.channels).mean(axis=1)

    board = Pedalboard()

    # Check for !normal: command first to reset all effects for this segment
    if any(cmd.startswith("!normal:") for cmd in commands):
        print(f"DEBUG: !normal: command detected. Skipping other DSP effects for this segment.")
        # No effects applied, return original audio data
    else:
        for cmd in commands:
            if cmd.startswith("!echo:"):
                # Pedalboard Delay effect
                board.append(Delay(delay_seconds=0.3, feedback=0.4, mix=0.5))
            elif cmd.startswith("!hall:"):
                # Pedalboard Reverb effect
                board.append(Reverb(room_size=0.5, damping=0.5, wet_level=0.3, dry_level=0.7))
            elif cmd.startswith("!pitch+"):
                semitones = int(cmd.replace("!pitch+", "").replace(":", "")) if cmd.replace("!pitch+", "").replace(":", "").isdigit() else 2
                board.append(PitchShift(semitones=semitones))
            elif cmd.startswith("!pitch-"):
                semitones = int(cmd.replace("!pitch-", "").replace(":", "")) if cmd.replace("!pitch-", "").replace(":", "").isdigit() else -2
                board.append(PitchShift(semitones=-semitones)) # Negative semitones for pitch down
            elif cmd.startswith("!lowpass:"):
                try:
                    cutoff_str = cmd.replace("!lowpass:", "").strip()
                    cutoff = float(cutoff_str) if cutoff_str else 500.0
                    board.append(LowpassFilter(cutoff_frequency_hz=cutoff))
                except ValueError:
                    print(f"Invalid cutoff frequency for !lowpass: {cmd}. Using default 500Hz.")
                    board.append(LowpassFilter(cutoff_frequency_hz=500.0))
            elif cmd.startswith("!highpass:"):
                try:
                    cutoff_str = cmd.replace("!highpass:", "").strip()
                    cutoff = float(cutoff_str) if cutoff_str else 2000.0
                    board.append(HighpassFilter(cutoff_frequency_hz=cutoff))
                except ValueError:
                    print(f"Invalid cutoff frequency for !highpass: {cmd}. Using default 2000Hz.")
                    board.append(HighpassFilter(cutoff_frequency_hz=2000.0))
            elif cmd.startswith("!tremolo:"):
                # board.append(Tremolo(rate=3.0, depth=0.5)) # Commented out due to import issues
                print(f"DEBUG: Tremolo effect skipped due to import issues: {cmd}")
                pass
            elif cmd.startswith("!flanger:"):
                # board.append(Flanger(rate=0.25, depth=1.0, mix=0.5, feedback=0.0, delay_time=0.003)) # Commented out due to import issues
                print(f"DEBUG: Flanger effect skipped due to import issues: {cmd}")
                pass
            elif cmd.startswith("!chorus:"):
                # board.append(Chorus(rate=1.5, depth=0.7, centre_delay=0.03, feedback=0.25, mix=0.5)) # Commented out due to import issues
                print(f"DEBUG: Chorus effect skipped due to import issues: {cmd}")
                pass
            elif cmd.startswith("!overdrive:"):
                # board.append(Overdrive(drive_db=45.0)) # Commented out due to import issues
                print(f"DEBUG: Overdrive effect skipped due to import issues: {cmd}")
                pass
            elif cmd.startswith("!reverse:"):
                # Pedalboard does not have a direct reverse effect.
                # This would require manual manipulation of the numpy array.
                # For now, we'll skip it or implement it separately if critical.
                print(f"DEBUG: Reverse effect not directly supported by Pedalboard. Skipping: {cmd}")
                pass
            else:
                print(f"Unknown DSP command: {cmd}")

    # Apply effects
    # Ensure audio_data is 2D (channels, samples) for pedalboard
    if audio_data.ndim == 1:
        audio_data = audio_data.reshape(1, -1) # Convert mono to (1, samples)

    processed_audio_data = board(audio_data, sample_rate)

    # Convert processed numpy array back to pydub AudioSegment
    # Ensure processed_audio_data is 1D for pydub
    if processed_audio_data.ndim > 1:
        processed_audio_data = processed_audio_data.flatten()

    # Convert back to 16-bit integer for pydub
    processed_audio_data = np.clip(processed_audio_data * (2**15), - (2**15), (2**15) - 1).astype(np.int16)

    return AudioSegment(
        processed_audio_data.tobytes(), 
        frame_rate=sample_rate,
        sample_width=2, # 16-bit
        channels=1 # Assuming mono after processing
    )
