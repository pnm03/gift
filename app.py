import os
from flask import Flask, redirect, url_for, request, render_template, flash, session
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
    # Sử dụng cascade để tự động xóa các bản ghi Selection khi GiftBox bị xóa
    selection = db.relationship('Selection', backref='gift', uselist=False, cascade="all, delete-orphan")

# Model lưu thông tin lựa chọn quà của người dùng
class Selection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    student_code = db.Column(db.String(50), nullable=False, unique=True)
    gift_box_id = db.Column(db.Integer, db.ForeignKey("gift_box.id"), nullable=False)

# Tạo bảng ngay khi module được import (để Gunicorn có thể sử dụng)
with app.app_context():
    db.create_all()

@app.route("/")
def index():
    gift_boxes = GiftBox.query.all()
    return render_template("index.html", gift_boxes=gift_boxes)

@app.route("/result/<int:gift_id>")
def result(gift_id):
    gift = GiftBox.query.get_or_404(gift_id)
    if not gift.selection:
        flash("Hộp quà này chưa được chọn, bạn không thể xem chi tiết!")
        return redirect(url_for("index"))
    return render_template("result.html", gift=gift, selection=gift.selection)

@app.route("/select/<int:gift_id>", methods=["GET", "POST"])
def select_gift(gift_id):
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

# Route admin xóa hộp quà
@app.route("/admin/delete/<int:gift_id>", methods=["POST"])
def delete_gift(gift_id):
    if not session.get("admin"):
        flash("Bạn không có quyền xóa!")
        return redirect(url_for("admin_login"))
    
    gift = GiftBox.query.get_or_404(gift_id)
    # Nếu gift đã có người chọn, bạn có thể cảnh báo hoặc cho phép xóa
    db.session.delete(gift)
    db.session.commit()
    flash("Hộp quà đã được xóa!")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
