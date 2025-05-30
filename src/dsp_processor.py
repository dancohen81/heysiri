import re
import numpy as np
from scipy.io import wavfile
from scipy import signal
import os
import uuid
from pydub import AudioSegment

def _split_text_by_commands(text: str):
    """
    Splits the input text into segments based on DSP commands.
    Each segment is a dictionary with 'text' and 'commands'.
    Commands apply to the text segment that follows them.
    """
    # Regex to find commands anywhere in the string
    # Example: !echo: !hall: This is text !pitch+: more text
    command_pattern = re.compile(r"(!(?:echo|hall|pitch[+-]?|lowpass|highpass|normal):)\s*")
    
    segments = []
    last_idx = 0
    current_commands = []

    # Find all command occurrences
    matches = list(command_pattern.finditer(text))

    for match in matches:
        cmd_start = match.start()
        cmd_end = match.end()
        cmd = match.group(1)

        # If there's text before this command, it belongs to the previous segment's commands
        if cmd_start > last_idx:
            segment_text = text[last_idx:cmd_start].strip()
            if segment_text:
                segments.append({"text": segment_text, "commands": list(current_commands)})
            current_commands = [] # Reset commands for the new segment
        
        current_commands.append(cmd)
        last_idx = cmd_end
    
    # Add the last segment
    remaining_text = text[last_idx:].strip()
    if remaining_text or current_commands: # Even if no text, if there are commands, they apply to an empty segment
        segments.append({"text": remaining_text, "commands": list(current_commands)})
    
    return segments

def parse_dsp_commands(ai_response: str):
    """
    Parses DSP commands from an AI response, allowing them anywhere in the text.
    Returns a list of dictionaries, where each dictionary contains a text segment
    and a list of commands that apply to that segment.
    """
    return _split_text_by_commands(ai_response)

def apply_echo(audio_data: np.ndarray, sample_rate: int, delay_ms: int = 200, decay: float = 0.5) -> np.ndarray:
    """Applies an echo effect to the audio data, allowing the echo to decay beyond the original length."""
    if not audio_data.size:
        return audio_data
    
    delay_samples = int(sample_rate * delay_ms / 1000)
    
    # Determine the length of the echo tail.
    # Let's estimate a tail duration, e.g., 1 second or 3 * delay_ms, whichever is larger.
    echo_tail_duration_ms = max(1000, delay_ms * 3) 
    echo_tail_samples = int(sample_rate * echo_tail_duration_ms / 1000)

    # The new length of the audio will be original length + echo tail length
    new_length = len(audio_data) + echo_tail_samples
    echoed_audio = np.zeros(new_length, dtype=np.float64)
    
    audio_data_float = audio_data.astype(np.float64)

    # Copy original audio to the beginning of the new array
    echoed_audio[:len(audio_data_float)] = audio_data_float

    # Apply the echo effect
    # The echo will be added to the original audio and extend into the padded area
    # This loop applies multiple echoes
    current_decay_factor = 1.0
    for i in range(1, 10): # Apply up to 10 echoes, or until decay is too small
        current_delay_samples = delay_samples * i
        current_decay_factor *= decay
        
        if current_decay_factor < 0.01: # Stop if echo is too quiet
            break
        
        if current_delay_samples < new_length:
            # Calculate the portion of the original audio that will be echoed at this delay
            source_start = 0
            source_end = len(audio_data_float)
            
            # Calculate the destination in the echoed_audio array
            dest_start = current_delay_samples
            dest_end = min(new_length, current_delay_samples + len(audio_data_float))
            
            # Ensure source and destination slices match length
            slice_length = min(len(audio_data_float), new_length - current_delay_samples)
            
            echoed_audio[dest_start : dest_start + slice_length] += audio_data_float[source_start : source_start + slice_length] * current_decay_factor

    # Normalize to prevent clipping
    max_val = np.max(np.abs(echoed_audio))
    if max_val > 1.0:
        echoed_audio /= max_val

    return echoed_audio.astype(audio_data.dtype)

def apply_reverb(audio_data: np.ndarray, sample_rate: int, decay_ms: int = 1000, num_echoes: int = 5, initial_decay: float = 0.6) -> np.ndarray:
    """Applies a simplified reverb effect using multiple decaying echoes."""
    if not audio_data.size:
        return audio_data

    reverb_audio = audio_data.astype(np.float64)
    current_decay = initial_decay
    
    for i in range(1, num_echoes + 1):
        delay_ms = int(decay_ms / num_echoes * i)
        reverb_audio = apply_echo(reverb_audio, sample_rate, delay_ms, current_decay)
        current_decay *= 0.7 # Further decay for subsequent echoes
        
    return reverb_audio.astype(audio_data.dtype)

def apply_pitch_shift(audio_data: np.ndarray, sample_rate: int, semitones: int) -> np.ndarray:
    """
    Applies a simple pitch shift by resampling.
    Note: This will also change the tempo. For true pitch shift without tempo change,
    more advanced algorithms (e.g., PSOLA) or libraries like pydub/librosa are needed.
    """
    if not audio_data.size:
        return audio_data

    factor = 2**(semitones / 12.0)
    original_length = len(audio_data)
    
    # Resample
    resampled_audio = signal.resample(audio_data, int(original_length / factor))
    
    # Pad or truncate to original length (this will affect tempo)
    if len(resampled_audio) < original_length:
        padded_audio = np.zeros(original_length, dtype=resampled_audio.dtype)
        padded_audio[:len(resampled_audio)] = resampled_audio
        return padded_audio
    else:
        return resampled_audio[:original_length]

def apply_filter(audio_data: np.ndarray, sample_rate: int, filter_type: str, cutoff_freq: float) -> np.ndarray:
    """Applies a Butterworth filter (low-pass or high-pass)."""
    if not audio_data.size:
        return audio_data

    nyquist = 0.5 * sample_rate
    normal_cutoff = cutoff_freq / nyquist
    
    if normal_cutoff >= 1.0 or normal_cutoff <= 0.0:
        print(f"Warning: Cutoff frequency {cutoff_freq} Hz is out of valid range for filter type {filter_type}. Skipping filter.")
        return audio_data

    b, a = signal.butter(5, normal_cutoff, btype=filter_type, analog=False)
    filtered_audio = signal.lfilter(b, a, audio_data)
    return filtered_audio.astype(audio_data.dtype)

import math

def _apply_effects_to_segment(audio_segment: AudioSegment, commands: list) -> AudioSegment:
    """
    Applies DSP effects to a single pydub AudioSegment.
    """
    if not audio_segment.duration_seconds:
        return audio_segment

    sample_rate = audio_segment.frame_rate
    
    # Convert pydub AudioSegment to numpy array for processing
    audio_data = np.array(audio_segment.get_array_of_samples())
    
    # If stereo, convert to mono by taking the first channel or averaging
    if audio_segment.channels > 1:
        audio_data = audio_data[::audio_segment.channels] 

    # Convert to float for processing
    if audio_segment.sample_width == 2: # 16-bit
        audio_data = audio_data.astype(np.float32) / (2**15)
    elif audio_segment.sample_width == 4: # 32-bit
        audio_data = audio_data.astype(np.float32) / (2**31)
    else: # Fallback for other sample widths, normalize to -1.0 to 1.0
        audio_data = audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max

    processed_audio_data = audio_data

    # Check for !normal: command first to reset all effects for this segment
    if any(cmd.startswith("!normal:") for cmd in commands):
        processed_audio_data = audio_data # Revert to original audio for this segment
        print(f"DEBUG: !normal: command detected. Skipping other DSP effects for this segment.")
        # No need to process other commands if !normal: is present
        # However, other commands might be in the list, so we need to ensure they don't apply.
        # The simplest is to just set processed_audio_data and then break.
    else:
        for cmd in commands:
            if cmd.startswith("!echo:"):
                processed_audio_data = apply_echo(processed_audio_data, sample_rate)
            elif cmd.startswith("!hall:"): # Using !hall: for reverb
                processed_audio_data = apply_reverb(processed_audio_data, sample_rate)
            elif cmd.startswith("!pitch+"):
                semitones = int(cmd.replace("!pitch+", "").replace(":", "")) if cmd.replace("!pitch+", "").replace(":", "").isdigit() else 2
                processed_audio_data = apply_pitch_shift(processed_audio_data, sample_rate, semitones)
            elif cmd.startswith("!pitch-"):
                semitones = int(cmd.replace("!pitch-", "").replace(":", "")) if cmd.replace("!pitch-", "").replace(":", "").isdigit() else -2
                processed_audio_data = apply_pitch_shift(processed_audio_data, sample_rate, -semitones) # Negative semitones for pitch-
            elif cmd.startswith("!lowpass:"):
                try:
                    # Extract cutoff frequency, default to 500 if not provided or invalid
                    cutoff_str = cmd.replace("!lowpass:", "").strip()
                    cutoff = float(cutoff_str) if cutoff_str else 500.0
                    processed_audio_data = apply_filter(processed_audio_data, sample_rate, "lowpass", cutoff)
                except ValueError:
                    print(f"Invalid cutoff frequency for !lowpass: {cmd}. Using default 500Hz.")
                    processed_audio_data = apply_filter(processed_audio_data, sample_rate, "lowpass", 500.0)
            elif cmd.startswith("!highpass:"):
                try:
                    # Extract cutoff frequency, default to 2000 if not provided or invalid
                    cutoff_str = cmd.replace("!highpass:", "").strip()
                    cutoff = float(cutoff_str) if cutoff_str else 2000.0
                    processed_audio_data = apply_filter(processed_audio_data, sample_rate, "highpass", cutoff)
                except ValueError:
                    print(f"Invalid cutoff frequency for !highpass: {cmd}. Using default 2000Hz.")
                    processed_audio_data = apply_filter(processed_audio_data, sample_rate, "highpass", 2000.0)
            else:
                print(f"Unknown DSP command: {cmd}")

    # Convert processed numpy array back to pydub AudioSegment
    # Determine the target sample width based on the original audio segment
    target_sample_width = audio_segment.sample_width

    if target_sample_width == 2: # 16-bit
        processed_audio_data = np.clip(processed_audio_data * (2**15), - (2**15), (2**15) - 1).astype(np.int16)
    elif target_sample_width == 4: # 32-bit
        processed_audio_data = np.clip(processed_audio_data * (2**31), - (2**31), (2**31) - 1).astype(np.int32)
    else: # Fallback to 16-bit if original was not 2 or 4 bytes
        processed_audio_data = np.clip(processed_audio_data * (2**15), - (2**15), (2**15) - 1).astype(np.int16)
        target_sample_width = 2

    return AudioSegment(
        processed_audio_data.tobytes(), 
        frame_rate=sample_rate,
        sample_width=target_sample_width,
        channels=1 # Assuming mono after processing
    )
