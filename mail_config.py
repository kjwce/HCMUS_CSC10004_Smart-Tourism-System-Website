# mail_config.py
from flask_mailman import Mail

def init_mail(app):
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'isukixyz1006@gmail.com'        # ← Gmail thật của bạn
    app.config['MAIL_PASSWORD'] = 'rsqhtsfzylytvamo'      # ← App Password (16 ký tự)
    app.config['MAIL_DEFAULT_SENDER'] = ('FoodieFinds', 'isukixyz1006@gmail.com')
    return Mail(app)
