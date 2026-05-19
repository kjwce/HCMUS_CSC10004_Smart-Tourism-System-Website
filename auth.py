from flask import Blueprint, request, jsonify, redirect, url_for, session, render_template, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import sqlite3
from flask_mailman import EmailMessage
from mail_config import init_mail
import random
import time


auth_bp = Blueprint('auth', __name__)
DATABASE = 'users.db'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

mail = None  # biến mail toàn cục

# Hàm tạo database user (chạy 1 lần đầu)
def init_user_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        verified INTEGER DEFAULT 0,
        avatar TEXT DEFAULT 'default-avatar.png'
    )''')
    conn.commit()
    conn.close()

import time  # ⭐ BẮT BUỘC PHẢI THÊM
from flask import Blueprint, request, jsonify, redirect, url_for, session, render_template
from werkzeug.security import generate_password_hash
import sqlite3
import random
from flask_mailman import EmailMessage

auth_bp = Blueprint('auth', __name__)


# ========== ĐĂNG KÝ ==========
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 🔥 CHECK ANTI-SPAM NGAY TẠI ĐÂY
        now = int(time.time())
        last = session.get("last_register", 0)

        if now - last < 5:  # giới hạn 1 lần / 5s
            return render_template("signup.html", error="Bạn thao tác quá nhanh!")

        session["last_register"] = now
        # 🔥 HẾT PHẦN CHỐNG SPAM

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password2 = request.form.get('password2')   # ⭐ thêm kiểm tra

        # Kiểm tra đủ fields
        if not username or not email or not password:
            return render_template("signup.html", error="Thiếu thông tin!")

        # Kiểm tra mật khẩu nhập lại
        if password != password2:
            return render_template("signup.html", error="Mật khẩu nhập lại không khớp!")

        # Kiểm tra trùng email / username
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ? OR username = ?", (email, username))
        existing = c.fetchone()
        conn.close()

        if existing:
            return render_template("signup.html", error="Username hoặc email đã tồn tại!")

        # Tạo OTP
        otp = str(random.randint(100000, 999999))

        # Lưu thông tin vào session
        session['pending_user'] = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'otp': otp
        }

        # Ghi lại timestamp để chặn resend
        session['otp_time'] = int(time.time())

        # Gửi email OTP
        msg = EmailMessage(
            subject="FoodieFinds - Verify Email",
            body=f"Mã OTP của bạn là: {otp}",
            to=[email]
        )
        msg.send()

        # ⭐ Redirect ngay lập tức → tránh spam
        return redirect(url_for('auth.verify_otp'))

    return render_template("signup.html")


# ========== VERIFY OTP ==========
@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'GET':
        return render_template('verify.html')

    otp_input = request.form.get('otp', '').strip()

    pending = session.get('pending_user')
    if not pending:
        return render_template('verify.html', error='Không có đăng ký nào đang chờ xác thực!')

    if otp_input != pending['otp']:
        return render_template('verify.html', error='Mã OTP không đúng!')

    # Lưu user vào DB
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (username, email, password_hash, verified)
        VALUES (?, ?, ?, 1)
    ''', (pending['username'], pending['email'], pending['password_hash']))
    conn.commit()
    conn.close()

    # Xóa pending
    session.pop('pending_user', None)
    session.pop('otp_time', None)

    return render_template('login.html', message='Xác thực thành công! Hãy đăng nhập.')


# ========== RESEND OTP ==========
@auth_bp.route('/resend_otp')
def resend_otp():
    pending = session.get('pending_user')
    if not pending:
        return jsonify({'error': 'Không có đăng ký đang chờ!'}), 400

    now = int(time.time())
    last = session.get('otp_time', 0)

    # Chặn resend dưới 60s
    if now - last < 60:
        return jsonify({'error': 'Vui lòng đợi 60 giây để gửi lại OTP!'}), 429

    otp = str(random.randint(100000, 999999))
    pending['otp'] = otp
    session['otp_time'] = now

    msg = EmailMessage(
        subject="FoodieFinds - Resend OTP",
        body=f"Mã xác thực mới của bạn là: {otp}",
        to=[pending['email']]
    )
    msg.send()

    return jsonify({'message': 'OTP mới đã được gửi!'})

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    BLOCKED = ['/signup', '/verify', '/forgot', '/reset', '/login']

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].strip()

        # Lấy trang trước đó từ hidden input
        next_page = request.form.get("next")

        # Nếu referrer không có → về home
        if not next_page:
            next_page = url_for("home")

        # Nếu next_page chứa các route bị chặn → về home
        if any(b in next_page for b in BLOCKED):
            next_page = url_for("home")

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session['username'] = username
            session['email'] = user[2]
            session['avatar'] = user[5] if len(user) > 5 else None
            return redirect(next_page)

        return render_template('login.html', error='Sai tên đăng nhập hoặc mật khẩu!\nIncorrect username or password!')

    # GET → chỉ render login
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    next_page = request.args.get('next') or request.referrer or url_for('home')

    BLOCKED = ['/signup', '/verify', '/forgot', '/reset']

    # Nếu next dẫn tới trang đặc biệt → về home
    if any(b in next_page for b in BLOCKED):
        next_page = url_for('home')

    session.pop('username', None)
    session.pop('email', None)
    session.pop('avatar', None)

    return redirect(next_page)

def setup_mail(app):
    global mail
    mail = init_mail(app)
    print("✅ Mail initialized:", mail)

@auth_bp.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form.get('email')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()

        if not user:
            return render_template('forgot.html', error='Email không tồn tại!\nEmail does not exist!')

        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['email_reset'] = email

        # Gửi email thật
        msg = EmailMessage(
            subject="FoodieFinds - Password Reset Code",
            body=f"Xin chào {user[1]},\n\nMã xác nhận của bạn là: {otp}\n\nFoodieFinds Team",
            to=[email]
        )
        print("📩 Mail before send:", mail)
        msg.send()  # ✅ Flask-Mailman dùng cú pháp này
        
        return redirect(url_for('auth.reset_password'))

    return render_template('forgot.html')

@auth_bp.route('/reset', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        otp_input = request.form.get('otp')
        new_pass = request.form.get('new_password')
        confirm_pass = request.form.get('confirm_password')

        # Kiểm tra session có OTP và email không
        if 'otp' not in session or 'email_reset' not in session:
            return render_template('reset.html', error='OTP hết hạn hoặc chưa gửi!\nOTP expired or not sent!')
        # Kiểm tra OTP
        if otp_input != session['otp']:
            return render_template('reset.html', error='Mã OTP không đúng!\nOTP code is incorrect!')

        # Kiểm tra mật khẩu trùng khớp
        if new_pass != confirm_pass:
            return render_template('reset.html', error='Mật khẩu nhập lại không khớp!\nPasswords do not match!')
        # Cập nhật mật khẩu mới
        hashed = generate_password_hash(new_pass)
        email = session['email_reset']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('UPDATE users SET password_hash = ? WHERE email = ?', (hashed, email))
        conn.commit()
        conn.close()

        # Xóa OTP khỏi session
        session.pop('otp', None)
        session.pop('email_reset', None)

        return render_template('reset.html', message='✅ Mật khẩu đã được thay đổi thành công!\n✅ Password changed successfully!')

    return render_template('reset.html')

@auth_bp.route('/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify({'error': 'Bạn chưa đăng nhập!\nYou are not logged in!'}), 403

    data = request.get_json()
    current_pass = data.get('current_password', '').strip()
    new_pass = data.get('new_password', '').strip()

    if not current_pass or not new_pass:
        return jsonify({'error': 'Thiếu thông tin!\nMissing information!'}), 400

    username = session['username']

    # Lấy thông tin user
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Không tìm thấy người dùng!\nUser not found!'}), 404

    if not check_password_hash(row[0], current_pass):
        return jsonify({'error': 'Mật khẩu hiện tại không đúng!\nCurrent password is incorrect!'}), 400

    # Cập nhật mật khẩu mới
    new_hashed = generate_password_hash(new_pass)
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hashed, username))
    conn.commit()
    conn.close()

    return jsonify({'message': '✅ Password changed successfully!'})

# ========= UPLOAD AVATAR =========
@auth_bp.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'username' not in session:
        return jsonify({'error': 'Bạn chưa đăng nhập!\nYou are not logged in!'}), 403

    if 'avatar' not in request.files:
        return jsonify({'error': 'Không có file nào được gửi lên!\nNo file uploaded!'}), 400

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'Chưa chọn file!\nNo file selected!'}), 400

    # Chỉ cho phép các loại file ảnh
    allowed = {'png', 'jpg', 'jpeg', 'gif'}
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed:
        return jsonify({'error': 'Chỉ được upload file ảnh (png, jpg, jpeg, gif)!\nOnly image files (png, jpg, jpeg, gif) are allowed!'}), 400

    # Kết nối DB
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Lấy avatar cũ từ DB
    c.execute('SELECT avatar FROM users WHERE username = ?', (session['username'],))
    row = c.fetchone()
    old_avatar = row[0] if row else None

    # Xóa file avatar cũ nếu tồn tại
    if old_avatar:
        old_path = os.path.join(current_app.root_path, 'static', 'uploads', old_avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    # Đặt tên file mới theo username + đuôi
    filename = secure_filename(f"{session['username']}.{ext}")
    upload_path = os.path.join(current_app.root_path, 'static', 'uploads', filename)
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    session['avatar'] = filename


    # Lưu file mới
    file.save(upload_path)

    # Cập nhật DB
    c.execute('UPDATE users SET avatar = ? WHERE username = ?', (filename, session['username']))
    conn.commit()
    conn.close()

    return jsonify({
        'message': '✅ Ảnh đại diện đã được cập nhật!\n✅ Avatar updated successfully!',
        'avatar_url': url_for('static', filename=f'uploads/{filename}')
    })

