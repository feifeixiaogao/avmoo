# coding: utf-8

from leancloud import Object
from leancloud import User
from leancloud import Query
from leancloud import ACL
from leancloud import LeanCloudError
from flask import Blueprint
from flask import request
from flask import redirect
from flask import url_for
from flask import render_template
from flask import flash
# from lean_insert import LCMovieListClass

class MovieList(Object):
    pass

movies_view = Blueprint('movies', __name__)

# 显示所有 Todo
@movies_view.route('')
def show():
    # LCMovieListClass()
    try:
        movies = Query(MovieList).find()
    except LeanCloudError as e:
        movies = []
        flash(e.error)
    return render_template('movies.html', movies=movies)

# 新建一个 Todo
@todos_view.route('', methods=['POST'])
def add():
    LCMovieListClass()
    content = request.form['content']
    todo = Todo()
    todo.set('content', content)
    todo.set('status', PLANNED)
    author = User.get_current()
    if author:
        todo.set('author', author)  # 关联 todo 的作者
    try:
        todo.save()
    except LeanCloudError as e:
        flash(e.error)
    return redirect(url_for('todos.show'))