# coding: utf-8
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

import sqlite3
import requests
import json
# from lxml import etree
import time
import re
import math
import os
import binascii
# DB = conn()
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
            return movie(tmp)
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

@app.route('/movie/<linkid>')
def movie(linkid=''):
    if linkid=='':
        return redirect(url_for('index'), 404)
    if '-' in linkid:
        where = ' av_list.av_id="{}"'.format(linkid.upper())
    else:
        where = ' av_list.linkid="{}"'.format(linkid)
    sql_arr = sqliteSelect('*', 'av_list', where, (0, 1))

    if sql_arr[0] == []:
        return redirect(url_for('index'),404)
    
    movie = sql_arr[0][0]
    #系列
    if movie['genre']:
        movie['genre_list'] = movie['genre'].split('|')
    #演员
    if movie['stars_url']:
        sql = 'select linkid,name,headimg from av_stars where linkid in ("{}")'.format(
            movie['stars_url'].replace('|','","'))
        stars_data = querySql(sql)
        movie['stars_data'] = stars_data
    #图片
    img = []
    if movie['image_len'] != '0':
        count = int(movie['image_len'])
        imgurl = CDN_SITE + '/digital/video' + \
            movie['bigimage'].replace('pl.jpg', '')
        for i in range(1, count+1):
            img.append({
                'small':'{}-{}.jpg'.format(imgurl, i),
                'big':'{}jp-{}.jpg'.format(imgurl, i)
            })
    else:
        img = ''
    movie['imglist'] = img
    return render_template('movie.html', data=movie, cdn=CDN_SITE)

@app.route('/director/<keyword>')
@app.route('/director/<keyword>/page/<int:pagenum>')
@app.route('/studio/<keyword>')
@app.route('/studio/<keyword>/page/<int:pagenum>')
@app.route('/label/<keyword>')
@app.route('/label/<keyword>/page/<int:pagenum>')
@app.route('/series/<keyword>')
@app.route('/series/<keyword>/page/<int:pagenum>')
@app.route('/genre/<keyword>')
@app.route('/genre/<keyword>/page/<int:pagenum>')
@app.route('/stars/<keyword>')
@app.route('/stars/<keyword>/page/<int:pagenum>')
def search(keyword='', pagenum = 1):
    if pagenum < 1:
        return redirect(url_for('index'), 404)
    limit_start = (pagenum - 1) * PAGE_LIMIT

    function = request.path.split('/')[1]
    if function == 'director' or function == 'studio' or function == 'label' or function == 'series' or function == 'stars':
        where = 'av_list.{}_url="{}"'.format(function, keyword)
    if function == 'genre':
        where = 'av_list.{} LIKE "%{}%"'.format(function, keyword)

    page_root = '/{}/{}'.format(function, keyword)
    result = sqliteSelect('*', 'av_list', where, (limit_start, PAGE_LIMIT))

    if function == 'stars':
        keyword = querySql(
            'SELECT name FROM "av_stars" where linkid="{}";'.format(keyword))[0]['name']
    
    if function != 'genre' and function != 'stars':
        keyword = ''

    return render_template('index.html', data=result[0], cdn=CDN_SITE, pageroot=page_root, page=pagination(pagenum, result[1]), keyword=keyword)

@app.route('/genre')
def genre():
    result = sqliteSelect('name,title','av_genre',1,(0,500),'',subtitle=False)
    data = {}
    for item in result[0]:
        if item['title'] not in data:
            data[item['title']] = []
        data[item['title']].append(item)
    data = list(data.values())
    return render_template('genre.html', data=data, cdn=CDN_SITE)

@app.route('/like/add/<data_type>/<data_val>')
def like_add(data_type=None, data_val=None):
    if data_type != None and data_val != None:
        timetext = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        sqltext = 'REPLACE INTO av_like VALUES("{}", "{}", "{}")'.format(
            data_type, data_val, timetext)
        DB['CUR'].execute(sqltext)
        DB['CONN'].commit()
        return 'ok'

@app.route('/like/del/<data_type>/<data_val>')
def like_del(data_type=None, data_val=None):
    if data_type != None and data_val != None:
        sqltext = 'DELETE FROM av_like WHERE type="{}" and val="{}"'.format(
            data_type, data_val)
        print(sqltext)
        DB['CUR'].execute(sqltext)
        DB['CONN'].commit()
        return 'ok'

@app.route('/like/movie')
@app.route('/like/movie/page/<int:pagenum>')
def like_page(pagenum=1):
    if pagenum < 1:
        return redirect(url_for('index'), 404)
    limit_start = (pagenum - 1) * PAGE_LIMIT

    result = sqliteSelect(column='*', table='av_list', limit=(limit_start, PAGE_LIMIT),
                          othertable=" JOIN av_like ON av_like.type='av_id' AND av_like.val = av_list.av_id ", order='av_like.time DESC')

    return render_template('index.html', data=result[0], cdn=CDN_SITE, pageroot='/like/movie', page=pagination(pagenum, result[1]), keyword='收藏影片')

@app.route('/like/<keyword>')
def like_page_other(keyword=''):
    map_ = {
        'director':'导演',
        'studio':'制作',
        'label':'发行',
        'series':'系列',
    }
    sqltext = "SELECT av_list.* FROM av_like JOIN (SELECT * FROM av_list GROUP BY {0}_url ORDER BY id DESC )av_list ON av_like.type='{0}' AND av_like.val=av_list.{0}_url".format(
        keyword
    )
    result = querySql(sqltext)
    return render_template('like.html', data=result, cdn=CDN_SITE, type_nick=map_[keyword], type_name=keyword, type_url=keyword + '_url', keyword='收藏'+map_[keyword])

@app.route('/like/stars')
def like_stars():
    sqltext = 'SELECT s.linkid,s.name,s.headimg,l.time FROM "av_like" l join "av_stars" s on l.val=s.linkid where l.type="stars" order by l.time desc'
    result = querySql(sqltext)
    return render_template('stars.html', data=result, cdn=CDN_SITE, keyword='收藏明星')

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

# if __name__ == '__main__':
#     DB = conn()
    # app.run(port = 5000)