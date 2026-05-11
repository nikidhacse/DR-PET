from transformers import AutoFeatureExtractor, ASTForAudioClassification
import torch

try:
    model_name = "MIT/ast-finetuned-audioset-10-10-0.4593"
    print(f"Loading {model_name}...")
    feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)
    model = ASTForAudioClassification.from_pretrained(model_name)
    print("Model loaded successfully!")
except Exception as e:
    print(f"Error: {e}")
