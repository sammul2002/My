import sqlite3 
import uuid
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
import os

# Flask 앱 설정
app = Flask(__name__)
app.config['SECRET_KEY'] = 'this-is-a-very$strong%secret!key123'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# 보안 기능 초기화
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)  # CSRF 보호 활성화

DATABASE = 'market.db'

# 데이터베이스 연결
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 테이블 생성
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                bio TEXT,
                status TEXT DEFAULT 'active'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                price TEXT NOT NULL,
                seller_id TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report (
                id TEXT PRIMARY KEY,
                reporter_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                reason TEXT NOT NULL
            )
        """)
        db.commit()

# 기본 라우트
@app.route('/')
def index():
    return render_template('index.html')

# 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        raw_password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(raw_password).decode('utf-8')

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        if cursor.fetchone():
            flash('이미 존재하는 사용자명입니다.')
            return redirect(url_for('register'))

        user_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO user (id, username, password) VALUES (?, ?, ?)",
                       (user_id, username, hashed_password))
        db.commit()
        flash('회원가입이 완료되었습니다.')
        return redirect(url_for('login'))
    return render_template('register.html')

# 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        input_password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and bcrypt.check_password_hash(user['password'], input_password):
            # 세션에 user_id를 저장
            session['user_id'] = user['id']
            session.permanent = True
            flash('로그인 성공!')
            print(f"User logged in: {user['username']}")  # 디버깅용 로그 출력
            return redirect(url_for('product_list'))  # 로그인 후 이동할 페이지

        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
        print(f"Login failed for username: {username}")  # 디버깅용 로그 출력
    return render_template('login.html')

# 로그아웃
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('로그아웃되었습니다.')
    return redirect(url_for('index'))

# 상품 목록 페이지
@app.route('/products')
def product_list():
    if 'user_id' not in session:
        flash('로그인이 필요합니다.')
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM product")
    products = cursor.fetchall()
    return render_template('product_list.html', products=products)

# 상품 등록
@app.route('/product/new', methods=['GET', 'POST'])
def new_product():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        product_id = str(uuid.uuid4())

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO product (id, title, description, price, seller_id) VALUES (?, ?, ?, ?, ?)",
                       (product_id, title, description, price, session['user_id']))
        db.commit()
        flash('상품이 등록되었습니다.')
        return redirect(url_for('product_list'))
    return render_template('new_product.html')

# 회원 정보 수정
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    cursor = db.cursor()
    user_id = session['user_id']
    
    if request.method == 'POST':
        new_bio = request.form['bio']
        cursor.execute("UPDATE user SET bio = ? WHERE id = ?", (new_bio, user_id))
        db.commit()
        flash('회원 정보가 수정되었습니다.')
        return redirect(url_for('profile'))

    cursor.execute("SELECT * FROM user WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    return render_template('profile.html', user=user)

# 상품 검색
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM product WHERE title LIKE ?", ('%' + query + '%',))
    products = cursor.fetchall()
    return render_template('product_list.html', products=products, query=query)

# 신고하기
@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        target_id = request.form['target_id']
        reason = request.form['reason']
        report_id = str(uuid.uuid4())

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO report (id, reporter_id, target_id, reason) VALUES (?, ?, ?, ?)",
                       (report_id, session['user_id'], target_id, reason))
        db.commit()
        flash('신고가 접수되었습니다.')
        return redirect(url_for('product_list'))
    return render_template('report.html')

# 앱 실행
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
