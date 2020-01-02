# coding: utf-8

import os

from flask import Flask
from flask import redirect
from flask import url_for
from flask import g
from flask import request
from flask import send_from_directory
from flask import flash
from flask import Markup
from flask import render_template
from werkzeug import Request
import leancloud

from views.todos import todos_view
from views.users import users_view


app = Flask(__name__)
app.config.update(dict(PREFERRED_URL_SCHEME='https'))
try:
    app.secret_key = bytes(os.environ.get('SECRET_KEY'), 'utf-8')
except TypeError:
    import sys
    sys.exit('未检测到密钥。请在 LeanCloud 控制台 > 云引擎 > 设置中新增一个名为 SECRET_KEY 的环境变量，再重试部署。')


class HTTPMethodOverrideMiddleware(object):
    """
    使用中间件以接受标准 HTTP 方法
    详见：https://gist.github.com/nervouna/47cf9b694842134c41f59d72bd18bd6c
    """

    allowed_methods = frozenset(['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    bodyless_methods = frozenset(['GET', 'HEAD', 'DELETE', 'OPTIONS'])

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        request = Request(environ)
        method = request.args.get('METHOD', '').upper()
        if method in self.allowed_methods:
            method = method.encode('ascii', 'replace')
            environ['REQUEST_METHOD'] = method
        if method in self.bodyless_methods:
            environ['CONTENT_LENGTH'] = 0
        return self.app(environ, start_response)

# 注册中间件
app.wsgi_app = HTTPMethodOverrideMiddleware(app.wsgi_app)
app.wsgi_app = leancloud.HttpsRedirectMiddleware(app.wsgi_app)
app.wsgi_app = leancloud.engine.CookieSessionMiddleware(app.wsgi_app, app.secret_key)

# 动态路由
app.register_blueprint(todos_view, url_prefix='/todos')
app.register_blueprint(users_view, url_prefix='/users')


@app.before_request
def before_request():
    g.user = leancloud.User.get_current()


# @app.route('/')
# def index():
#     return redirect(url_for('todos.show'))


@app.route('/help')
def help():
    return render_template('help.html')


@app.route('/robots.txt')
@app.route('/favicon.svg')
@app.route('/favicon.ico')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])


import sqlite3
import requests
import json
# from lxml import etree
import time
import re
import math
import os
import binascii

#每页展示的数量
PAGE_LIMIT = 30
CDN_SITE = '//jp.netcdn.space'
CDN_SITE = '//pics.dmm.co.jp'
#缓存
SQL_CACHE = {}
IF_USE_CACHE = True
@app.route('/')
@app.route('/page/<int:pagenum>')
@app.route('/search/<keyword>')
@app.route('/search/<keyword>/page/<int:pagenum>')
def index(keyword = '', pagenum = 1):
    if pagenum < 1:
        redirect(url_for('/'))
    limit_start = (pagenum -1) * PAGE_LIMIT
    keyword = keyword.replace("'",'').replace('"','').strip()

    #识别番号
    if re.match('^[a-zA-Z0-9 \-]{4,14}$', keyword):
        tmp = keyword.replace(' ', '-').upper()
        if '-' in tmp:
            # return movie(tmp)
            return 'movie(tmp)'
        else:
            where = 'av_list.av_id like "%{}%"'.format(tmp)
    #搜索
    elif keyword != '':
        where = ''
        key_list = keyword.split(' ')
        like_dict = {
            '收藏影片': 'av_id',
            '收藏导演': 'director_url',
            '收藏制作': 'studio_url',
            '收藏发行': 'label_url',
            '收藏系列': 'series_url',
            # '收藏明星': 'stars_url'
        }
        for key_item in key_list:
            if key_item == '字幕':
                where += ' av_163sub.sub_id IS NOT NULL and'
                continue
            if key_item == '已发布':
                date = time.strftime("%Y-%m-%d", time.localtime())
                where += ' av_list.release_date <= "{}" and'.format(date)
                continue
            if key_item in like_dict.keys():
                sql = 'SELECT val FROM av_like WHERE type="{}"'.format(
                    like_dict[key_item])
                data = querySql(sql)
                like_list = [x['val'] for x in data]
                where += ' av_list.{} in ("{}") and'.format(
                    like_dict[key_item],'","'.join(like_list))
                continue
            if key_item == '收藏明星':
                sql = 'SELECT val FROM av_like WHERE type="stars"'
                data = querySql(sql)
                item_list = ['av_list.stars_url like "%{}%"'.format(x['val']) for x in data]
                where += '({}) and'.format(' or '.join(item_list))
                continue
            where += '''
            (av_list.title like "%{0}%" or
            av_list.av_id like "%{0}%" or
            av_list.director = "{0}" or
            av_list.studio = "{0}" or
            av_list.label like "%{0}%" or
            av_list.series like "%{0}%" or
            av_list.genre like "%{0}%" or
            av_list.stars like "%{0}%")and'''.format(key_item)
        where = where[:-3]
    elif keyword == '':
        where = '1'
    result = sqliteSelect('*', 'av_list', where, (limit_start, PAGE_LIMIT))
    if keyword != '':
        page_root = '/{}/{}'.format('search', keyword)
    else:
        page_root = ''
    return render_template('index.html', data=result[0], cdn=CDN_SITE, pageroot=page_root, page=pagination(pagenum, result[1]), keyword=keyword)

def pagination(pagenum, count):
    pagecount = math.ceil(count / PAGE_LIMIT)
    if pagecount <= 15:
        p1 = 1
        p2 = pagecount
    else:
        if pagenum - 7 < 1:
            p1 = 1
        else:
            p1 = pagenum - 7
        if pagenum + 7 > pagecount:
            p2 = pagecount
        else:
            p2 = pagenum + 7

    pagelist = [x for x in range(p1, p2 + 1)]

    if pagenum != pagecount:
        pageright = pagenum + 1
    else:
        pageright = 0
    if pagenum != 1:
        pageleft = pagenum -1
    else:
        pageleft = 0
    
    return {
        'now': pagenum,
        'left': pageleft,
        'right': pageright,
        'list': pagelist
    }

def conn(dbfile= 'avmoo.db'):
    if os.path.exists('avmoo_.db'):
        dbfile = 'avmoo_.db'
    CONN = sqlite3.connect(dbfile, check_same_thread=False)
    CUR = CONN.cursor()
    return {
        'CONN':CONN,
        'CUR':CUR,
    }

def sqliteSelect(column='*', table='av_list', where='1', limit=(0, 30), order='id DESC', subtitle = True, othertable = ''):
    #db = conn()
    if order.strip() == '':
        order = ''
    else:
        order = 'ORDER BY ' + order
    #是否需要查询字幕
    #LEFT JOIN (SELECT av_id,sub_id FROM av_163sub GROUP BY av_id)av_163sub ON av_list.av_id=av_163sub.av_id
    #,av_163sub.sub_id
    if subtitle:
        sqltext = 'SELECT av_list.{0} FROM av_list {3} WHERE {1} {2}'.format(
            column, where, order, othertable)
    else:
        sqltext = 'SELECT {} FROM {} WHERE {} {}'.format(
            column, table, where, order)
    sqllimit = ' LIMIT {},{}'.format(limit[0], limit[1])
    result = querySql(sqltext + sqllimit)
    res_count = querySql('SELECT COUNT(1) AS count FROM ({})'.format(sqltext))
    # print(res_count)
    return (result, res_count[0]['count'])
    
def querySql(sql):
    DB = conn()
    cacheKey = (binascii.crc32(sql.encode()) & 0xffffffff)
    #是否有缓存
    if cacheKey in SQL_CACHE.keys():
        print('SQL CACHE[{}]'.format(cacheKey))
        return SQL_CACHE[cacheKey][:]
    else:
        print('SQL EXEC[{}]:\n{}'.format(cacheKey, sql))
        DB['CUR'].execute(sql)
        ret = DB['CUR'].fetchall()
        # print(ret)
        ret = showColumnname(ret, DB['CUR'].description)
        # print(ret, DB['CUR'].description)
        
        if IF_USE_CACHE:
            SQL_CACHE[cacheKey] = ret
        return ret[:]
        
def showColumnname(data, description):
    result = []
    for row in data:
        row_dict = {}
        for i in range(len(description)):
            row_dict[description[i][0]] = row[i]
        #图片地址
        if 'bigimage' in row_dict.keys():
            row_dict['smallimage'] = row_dict['bigimage'].replace('pl.jpg', 'ps.jpg')
        result.append(row_dict)

    return result

