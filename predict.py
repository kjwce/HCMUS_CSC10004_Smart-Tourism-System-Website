# predict.py
import sys
import torch
import torch.nn as nn
from torchvision.models import convnext_tiny, ConvNeXt_Tiny_Weights
from PIL import Image
import os

def load_model():
    try:
        # Load class names
        with open("class_names.txt", "r", encoding="utf-8") as f:
            class_names = [line.strip() for line in f]
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load model
        model = convnext_tiny(weights=None)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(class_names))
        
        # Kiểm tra file model tồn tại
        if not os.path.exists("model_convnext_tiny.pth"):
            raise FileNotFoundError("Model file not found: model_convnext_tiny.pth")
            
        state_dict = torch.load("model_convnext_tiny.pth", map_location=device)
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()
        
        # Transform
        transform = ConvNeXt_Tiny_Weights.DEFAULT.transforms()
        
        return model, transform, class_names, device
    except Exception as e:
        print(f"Error loading model: {e}", file=sys.stderr)
        return None, None, None, None

def predict(image_path):
    try:
        # Kiểm tra file ảnh tồn tại
        if not os.path.exists(image_path):
            return f"Error: Image file not found: {image_path}"
            
        img = Image.open(image_path).convert("RGB")
        x = transform(img).unsqueeze(0).to(device)

        with torch.no_grad():
            output = model(x)
            _, pred = torch.max(output, 1)

        return class_names[pred.item()]
    except Exception as e:
        return f"Error during prediction: {str(e)}"

# Load model khi import
model, transform, class_names, device = load_model()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Nhận đường dẫn ảnh từ command line argument
        image_path = sys.argv[1]
        if model is None:
            print("Model not loaded properly", file=sys.stderr)
            sys.exit(1)
        result = predict(image_path)
        # CHỈ IN KẾT QUẢ CUỐI CÙNG, không in debug info
        print(result)
    else:
        # Chế độ interactive - có thể in debug ở đây
        if model is None:
            print("Model not loaded properly")
            sys.exit(1)
        img_path = input("Nhập đường dẫn file ảnh: ")
        result = predict(img_path)
        print(f"Kết quả dự đoán: {result}")