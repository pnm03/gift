import os
from datetime import datetime
from flask import Flask, redirect, url_for, request, render_template, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "postgresql://test_gift_user:qFbjqnJsMCyI1QO6XwnazWoXYTBjD0nE@dpg-cvdpab2n91rc73ba4h20-a/test_gift"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Model cho hộp quà
class GiftBox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=True)
    # Quan hệ 1-1 với Selection (mỗi hộp quà chỉ được chọn 1 lần)
    selection = db.relationship('Selection', backref='gift', uselist=False, cascade="all, delete-orphan")

# Model lưu thông tin lựa chọn quà của người dùng
class Selection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    student_code = db.Column(db.String(50), nullable=False, unique=True)
    gift_box_id = db.Column(db.Integer, db.ForeignKey("gift_box.id"), nullable=False)

# Model lưu cấu hình thời gian countdown (giả sử chỉ có 1 bản ghi)
class CountdownSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    target_time = db.Column(db.DateTime, nullable=False)

# Tạo bảng ngay khi module được import (để Gunicorn khởi chạy)
with app.app_context():
    db.create_all()

# API endpoint cho AJAX polling (cập nhật danh sách hộp quà)
@app.route("/api/gift_boxes")
def api_gift_boxes():
    gift_boxes = GiftBox.query.all()
    data = []
    for gift in gift_boxes:
        data.append({
            "id": gift.id,
            "name": gift.name,
            "selected": True if gift.selection else False,
            "student_name": gift.selection.student_name if gift.selection else None,
            "student_code": gift.selection.student_code if gift.selection else None,
        })
    return jsonify(data)

# Trang chủ: hiển thị countdown nếu chưa đến target time, ngược lại hiển thị danh sách hộp quà.
@app.route("/")
def index():
    countdown = CountdownSetting.query.first()
    now = datetime.utcnow()
    return render_template("index.html", gift_boxes=GiftBox.query.all(), countdown=countdown, now=now)

# Route để người dùng chọn quà (chỉ cho phép nếu thời gian đã đến)
@app.route("/select/<int:gift_id>", methods=["GET", "POST"])
def select_gift(gift_id):
    # Kiểm tra countdown
    countdown = CountdownSetting.query.first()
    now = datetime.utcnow()
    if countdown and now < countdown.target_time:
        flash("Chưa đến thời gian cho phép chọn quà!")
        return redirect(url_for("index"))
    
    gift = GiftBox.query.get_or_404(gift_id)
    if gift.selection:
        flash("Hộp quà này đã được chọn!")
        return redirect(url_for("result", gift_id=gift_id))
    
    if request.method == "POST":
        student_name = request.form.get("student_name")
        student_code = request.form.get("student_code")
        if not student_name or not student_code:
            flash("Vui lòng điền đầy đủ thông tin!")
            return redirect(url_for("select_gift", gift_id=gift_id))
        
        if Selection.query.filter_by(student_code=student_code).first():
            flash("Mã sinh viên của bạn đã chọn quà rồi!")
            return redirect(url_for("index"))
        
        selection = Selection(
            student_name=student_name,
            student_code=student_code,
            gift_box_id=gift_id
        )
        db.session.add(selection)
        db.session.commit()
        flash("Chọn quà thành công!")
        return redirect(url_for("result", gift_id=gift_id))
    
    return render_template("select.html", gift=gift)

@app.route("/result/<int:gift_id>")
def result(gift_id):
    gift = GiftBox.query.get_or_404(gift_id)
    if not gift.selection:
        flash("Hộp quà này chưa được chọn, bạn không thể xem chi tiết!")
        return redirect(url_for("index"))
    return render_template("result.html", gift=gift, selection=gift.selection)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "123456":
            session["admin"] = True
            return redirect(url_for("add_gift"))
        else:
            flash("Thông tin đăng nhập không chính xác!")
            return redirect(url_for("admin_login"))
    return render_template("admin_login.html")

@app.route("/admin/add", methods=["GET", "POST"])
def add_gift():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    if request.method == "POST":
        gift_name = request.form.get("gift_name")
        gift_content = request.form.get("gift_content")
        if gift_name:
            gift = GiftBox(name=gift_name, content=gift_content)
            db.session.add(gift)
            db.session.commit()
            flash("Hộp quà đã được thêm!")
            return redirect(url_for("index"))
    return render_template("admin_add.html")

# Route admin để xóa hộp quà (chỉ admin)
@app.route("/admin/delete/<int:gift_id>", methods=["POST"])
def delete_gift(gift_id):
    if not session.get("admin"):
        flash("Bạn không có quyền xóa!")
        return redirect(url_for("admin_login"))
    gift = GiftBox.query.get_or_404(gift_id)
    db.session.delete(gift)
    db.session.commit()
    flash("Hộp quà đã được xóa!")
    return redirect(url_for("index"))

# Route admin để set thời gian countdown
@app.route("/admin/set_time", methods=["GET", "POST"])
def set_time():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    countdown = CountdownSetting.query.first()
    if request.method == "POST":
        target_time_str = request.form.get("target_time")  # Định dạng: YYYY-MM-DDTHH:MM
        if target_time_str:
            # Chuyển đổi chuỗi thành datetime (giả sử UTC)
            target_time = datetime.strptime(target_time_str, "%Y-%m-%dT%H:%M")
            if countdown:
                countdown.target_time = target_time
            else:
                countdown = CountdownSetting(target_time=target_time)
                db.session.add(countdown)
            db.session.commit()
            flash("Thời gian countdown đã được cập nhật!")
            return redirect(url_for("index"))
        else:
            flash("Vui lòng nhập thời gian!")
    return render_template("admin_set_time.html", countdown=countdown)

if __name__ == "__main__":
    app.run(debug=True)
