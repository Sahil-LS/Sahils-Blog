import smtplib
from datetime import date
from functools import wraps

# flask imports
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

import os

OWN_EMAIL = "learning.python.sa@gmail.com"
OWN_PASSWORD = os.environ.get("EMAIL")

# in project imports
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# For user images in Comments section
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create Users Tables in DB
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_by")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    # Create reference to the User object, the "posts" refers to the posts protperty in the User class.
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    comment = db.Column(db.Text, nullable=False)

    # To join the "comments" table with "user" table
    comment_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    comment_by = relationship("User", back_populates="comments")

    # Tp join "comments" table with "blog_posts" table
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


db.create_all()


def admin_only(fn):
    @wraps(fn)
    def decorated_function(*args, **kwargs):
        if int(current_user.get_id()) != 1:
            return abort(404)
        return fn(*args, **kwargs)
    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            flash("Hey you have done this step already. Login here.")
            return redirect(url_for("login"))
        else:
            pw = generate_password_hash(request.form.get("password"), method="pbkdf2:sha256", salt_length=8)
            new_user = User(
                email=email,
                password=pw,
                name=request.form.get("name")
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=register_form, logged_in=current_user.is_authenticated,
                           current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if request.method == "POST":
        email = request.form.get("email")
        pw = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Something is not quite right with 'Email'. Try Again!!! Hey be careful with tyopo and CAPS 😉")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, pw):
            flash("Hey come on give me the same password")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))
    return render_template("login.html", form=login_form, logged_in=current_user.is_authenticated)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    comments = Comment.query.filter_by(post_id=post_id).all()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("I must know you for you to comment. Please 'Login' or 'Register'. Thanks! ")
            return redirect(url_for("login"))
        new_comment = Comment(
            comment=request.form.get("comment_text"),
            parent_post=requested_post,
            comment_by=current_user
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id))
    return render_template("post.html", post=requested_post, logged_in=current_user.is_authenticated, form=comment_form,
                           comments=comments)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        s_n = request.form['sender_name']
        s_e = request.form['sender_email']
        s_p = request.form['sender_phone']
        s_m = request.form['sender_msg']
        send_email(s_n, s_e, s_p, s_m)
        return render_template("contact.html", msg_sent=True, h="Successfully sent your message")
    return render_template("contact.html", msg_sent=False, h="Contact Me")


def send_email(name, email, phone, message):
    email_message = f"Subject:New Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage:{message}"
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(OWN_EMAIL, OWN_PASSWORD)
        connection.sendmail(OWN_EMAIL, OWN_EMAIL, email_message)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author.name,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
