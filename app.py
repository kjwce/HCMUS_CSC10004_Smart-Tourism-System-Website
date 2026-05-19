from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from auth import auth_bp, init_user_db, setup_mail
from chatbox import chatbox_bp  # Import blueprint thay vì app
from search import search_bp 
from comments import comment_bp, init_comment_db
from community import community_bp, init_community_db
import subprocess
import os
import json
from werkzeug.utils import secure_filename
from favorites import favorite_bp, init_favorite_db 

# Khởi tạo Flask app
app = Flask(__name__)
CORS(app)
app.secret_key = "your_secret_key_here"

# Tạo database comments
init_comment_db()

# Tạo database community
init_community_db()

# Tạo database favorites
init_favorite_db()

# Đăng ký blueprint auth
app.register_blueprint(auth_bp, url_prefix="/auth")

# Đăng ký blueprint chatbox (QUAN TRỌNG!)
app.register_blueprint(chatbox_bp)

# Đăng ký blueprint search
app.register_blueprint(search_bp, url_prefix="/search_api")

# Đăng ký blueprint comment
app.register_blueprint(comment_bp)

# Đăng ký blueprint community
app.register_blueprint(community_bp)

# Đăng ký blueprint favorites
app.register_blueprint(favorite_bp)

# ===== DEBUG: in ra tất cả route =====
print("==== Route list ====")
for rule in app.url_map.iter_rules():
    print(rule)

# Tạo database nếu chưa có
init_user_db()
setup_mail(app)

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/login')
def form_login():
    return render_template('login.html')

@app.route('/signup')
def form_signup():
    return render_template('signup.html')

@app.route('/forgot')
def form_forgot():
    return render_template('forgot.html')

@app.route('/user')
def form_user():
    return render_template('user.html')

@app.route('/search')
def search():
    return render_template('search.html')

@app.route('/detail')
def detail():
    return render_template('detail.html')

@app.route('/restaurant')
def restaurant():
    return render_template('restaurant.html')

@app.route('/community')
def community():
    return render_template('community.html')

@app.route('/predict_food', methods=['POST'])
def predict_food_route():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        print(f"Received file: {file.filename}, size: {len(file.read())} bytes")
        file.seek(0)  # Reset file pointer sau khi đọc
        
        # Lưu file tạm thời
        filename = secure_filename(file.filename)
        temp_dir = 'temp_uploads'
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)
        
        print(f"Saved to: {temp_path}")
        print(f"Checking if file exists: {os.path.exists(temp_path)}")
        
        # Gọi file predict.py bằng subprocess
        try:
            print("Calling predict.py...")
            
            # Kiểm tra xem predict.py có tồn tại không
            if not os.path.exists('predict.py'):
                return jsonify({'error': 'predict.py not found'}), 500
            
            result = subprocess.run([
                'python', 'predict.py', temp_path
            ], capture_output=True, text=True, timeout=30)
            
            print(f"Predict result - returncode: {result.returncode}")
            print(f"Predict result - stdout: '{result.stdout}'")
            print(f"Predict result - stderr: '{result.stderr}'")
            
            if result.returncode == 0:
                prediction = result.stdout.strip()
                print(f"Prediction: {prediction}")
                
                # Xóa file tạm
                try:
                    os.remove(temp_path)
                except:
                    pass
                
                return jsonify({
                    'prediction': prediction,
                    'status': 'success'
                })
            else:
                print(f"Prediction failed with stderr: {result.stderr}")
                # Xóa file tạm
                try:
                    os.remove(temp_path)
                except:
                    pass
                
                return jsonify({
                    'error': f'Prediction failed: {result.stderr}'
                }), 500
                
        except subprocess.TimeoutExpired:
            print("Prediction timeout")
            # Xóa file tạm
            try:
                os.remove(temp_path)
            except:
                pass
            return jsonify({'error': 'Prediction timeout'}), 500
            
    except Exception as e:
        print(f"Exception in predict_food_route: {str(e)}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    
if __name__ == "__main__":
    print("🚀 Server chạy tại http://127.0.0.1:5000")
    app.run(debug=True)


