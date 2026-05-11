import librosa
import numpy as np
import torch
from transformers import AutoFeatureExtractor, ASTForAudioClassification
import os
from logger import get_logger

logger = get_logger("AcousticEngine")

class DrPetAcousticEngine:
    def __init__(self, model_name="MIT/ast-finetuned-audioset-10-10-0.4593"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)
            self.model = ASTForAudioClassification.from_pretrained(model_name).to(self.device)
            self.id2label = self.model.config.id2label
            logger.info(f"Acoustic Engine loaded AST on {self.device}")
        except Exception as e:
            logger.warning(f"Acoustic Model loading failed: {e}. Semantic classification disabled.")
            self.model = None

    def analyze_audio(self, audio_path):
        """
        Extracts Log-Mel Spectrograms and classifies animal vocalizations.
        Uses the AST transformer for high-accuracy bioacoustic inference.
        """
        if not os.path.exists(audio_path):
            return {"error": "Audio file not found"}

        try:
            # Load audio (librosa handles common video containers if ffmpeg is available)
            try:
                # Primary attempt: librosa load (works if ffmpeg/pysoundfile is present and container is simple)
                y, sr = librosa.load(audio_path, sr=16000, duration=10)
                is_proxy = False
            except Exception as e:
                logger.info(f"Direct librosa load failed for {audio_path}. Attempting ffmpeg extraction...")
                # Fallback: Extract audio via ffmpeg to a temporary wav
                import subprocess
                import tempfile
                
                temp_wav = os.path.join(tempfile.gettempdir(), f"drpet_audio_{os.path.basename(audio_path)}.wav")
                try:
                    # ffmpeg -i <video> -vn -acodec pcm_s16le -ar 16000 -ac 1 <output>
                    cmd = [
                        "ffmpeg", "-y", "-i", audio_path, 
                        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", 
                        "-t", "10", temp_wav
                    ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    y, sr = librosa.load(temp_wav, sr=16000)
                    is_proxy = False
                    if os.path.exists(temp_wav): os.remove(temp_wav)
                except Exception as fe:
                    logger.warning(f"Acoustic fallback failed: {fe}. Audio analysis bypassed.")
                    if os.path.exists(temp_wav): os.remove(temp_wav)
                    return {
                        "vocal_sentiment": "audio_unavailable",
                        "confidence": 0.0,
                        "is_proxy": False,
                        "fft_peaks": [],
                        "acoustic_signal_vector": [0, 0],
                        "status": "No valid audio track detected."
                    }

            # 1. Spectral Intelligence
            spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
            rms = np.mean(librosa.feature.rms(y=y))
            
            # 2. Deep Learning Inference (only if we have real audio or stable proxy)
            # Classification Map: Label -> Behavioral Significance
            sentiment = "UNCERTAIN"
            confidence = 0.0
            detected_labels = []

            if self.model and not is_proxy:
                inputs = self.feature_extractor(y, sampling_rate=sr, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    logits = self.model(**inputs).logits
                
                probs = torch.nn.functional.softmax(logits, dim=-1)
                top_prob, top_indices = torch.topk(probs, 5)
                
                for i in range(5):
                    label = self.id2label[top_indices[0][i].item()]
                    score = top_prob[0][i].item()
                    detected_labels.append({"label": label, "score": score})
                    
                # Deterministic Heuristic Fusion: ML Label + DSP Signal
                primary_label = detected_labels[0]["label"] if detected_labels else "None"
                
                if score > 0.3:
                    if any(x in primary_label for x in ["Bark", "Dog"]):
                        # High pitch/centroid = Bark of excitement vs deep protective bark
                        sentiment = "Affiliative / Playful" if spectral_centroid > 2800 else "Hyper-Aroused"
                    elif any(x in primary_label for x in ["Growl", "Snarl"]):
                        sentiment = "Defensive / Reactive"
                    elif any(x in primary_label for x in ["Whimper", "Cry", "Howl"]):
                        sentiment = "Suppressed / Pain State"
                    else:
                        sentiment = "Relaxed / Equilibrium" if rms < 0.05 else "Active"
                    confidence = score
            
            # 3. DSP Spectral Fallback (Rules-Based)
            if sentiment == "UNCERTAIN" or is_proxy:
                if rms > 0.12:
                    sentiment = "Hyper-Aroused"
                    confidence = 0.65
                elif spectral_centroid > 2600 and rms > 0.04:
                    sentiment = "Affiliative / Playful"
                    confidence = 0.70
                elif spectral_centroid < 1800 and rms > 0.06:
                    sentiment = "Defensive / Reactive" # Deep Growl profile
                    confidence = 0.75
                else:
                    sentiment = "Relaxed / Equilibrium"
                    confidence = 0.50

            # Debug Logging for Acoustic
            print(f"DEBUG [ACOUSTIC]: Sent: {sentiment} | Centroid: {spectral_centroid:.1f} | RMS: {rms:.4f} | ML: {detected_labels[0]['label'] if detected_labels else 'N/A'}")

            # 4. DSP Visualizer Data (FFT Peaks)
            # Higher resolution for the visualizer
            D = np.abs(librosa.stft(y))
            # Get the mean magnitude per frequency bin
            freq_magnitudes = np.mean(D, axis=1)
            # Select 20 representative peaks for the visualizer
            indices = np.linspace(0, len(freq_magnitudes)-1, 24).astype(int)
            fft_peaks = [float(f) for f in freq_magnitudes[indices]]

            return {
                "vocal_sentiment": sentiment,
                "acoustic_signal_vector": [float(spectral_centroid), float(rms)],
                "top_detections": detected_labels[:3],
                "confidence": round(float(confidence), 2),
                "fft_peaks": fft_peaks,
                "is_proxy": is_proxy,
                "status": "Acoustic signal processing complete"
            }
            
        except Exception as e:
            logger.error(f"Acoustic processing error: {e}", exc_info=True)
            return {
                "vocal_sentiment": "Unknown (Processing Error)",
                "acoustic_signal_vector": [0, 0],
                "confidence": 0.0
            }

