
import json
import pickle
import numpy as np
import os

def model_fn(model_dir):
    """Load model and preprocessing artifacts"""
    models = {}
    scaler = None
    label_encoder = None
    
    # Load model
    model_path = os.path.join(model_dir, "model.pkl")
    with open(model_path, "rb") as f:
        models["model"] = pickle.load(f)
    
    # Load scaler
    scaler_path = os.path.join(model_dir, "scaler.pkl")
    if os.path.exists(scaler_path):
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
    
    # Load label encoder
    encoder_path = os.path.join(model_dir, "label_encoder.pkl")
    if os.path.exists(encoder_path):
        with open(encoder_path, "rb") as f:
            label_encoder = pickle.load(f)
    
    return {
        "model": models["model"],
        "scaler": scaler,
        "label_encoder": label_encoder
    }


def input_fn(request_body, content_type="application/json"):
    """Parse input data"""
    if content_type == "application/json":
        data = json.loads(request_body)
        features = np.array(data["features"]).reshape(1, -1)
        return features
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model_dict):
    """Run prediction"""
    model = model_dict["model"]
    scaler = model_dict["scaler"]
    label_encoder = model_dict["label_encoder"]
    
    # Scale features
    if scaler is not None:
        input_data = scaler.transform(input_data)
    
    # Make prediction
    prediction = model.predict(input_data)[0]
    
    # Get probabilities if available
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(input_data)[0]
    else:
        proba = None
    
    # Decode label
    if label_encoder is not None:
        prediction_label = label_encoder.inverse_transform([prediction])[0]
    else:
        prediction_label = str(prediction)
    
    return {
        "prediction": prediction_label,
        "confidence": float(max(proba)) if proba is not None else 1.0,
        "probabilities": {label_encoder.classes_[i]: float(proba[i]) for i in range(len(proba))} if proba is not None and label_encoder is not None else {}
    }


def output_fn(prediction, accept="application/json"):
    """Format output"""
    if accept == "application/json":
        return json.dumps(prediction), accept
    else:
        raise ValueError(f"Unsupported accept type: {accept}")
