#-*-coding:utf8-*-
from lxml import etree
import leancloud
import requests

#1、获取网页数据
#2、解析所需要的内容
#3、插入数据库

class LCMovieListClass:
    def __init__(self):
        leancloud.init("a3ibT6vF8ItGtNpG5bKQd8gK-gzGzoHsz", "S2Nx8PCW4vYrVEfm9AlkGk5D")
        # self.page = 0
        # self.pagesize = 400
        self.movies = leancloud.Object.extend('MovieList')
        i = 1
        while i < 323:
            url = "http://www.4btbtt.com/forum-index-fid-1-page-{}.htm".format(i)
            movie.requestUrl(url)
            i+=1
        # query = obj.query
        # self.count = query.count()
        # self.getdata(query)
        # self.page

    def requestUrl(self,url):
        html = requests.get(url)
        selector = etree.HTML(html.text)
        #//*[@id="threadlist"]/table[32]/tr/td[1]/a[5]
        for item in selector.xpath('//*[@id="threadlist"]/table'):
            id = item.xpath('@tid')
            id = id[0] if len(id)>0 else ''
            #查询是否存在
            obj = leancloud.Object.extend('MovieList')
            query = obj.query
            query.equal_to('id', id)
            query_list = query.find()
            if len(query_list)!=0:
                print('已存在id:',id)
                return

            movietime = item.xpath('tr/td[1]/a[2]/text()')
            country = item.xpath('tr/td[1]/a[3]/text()')
            tp = item.xpath('tr/td[1]/a[4]/text()')
            title = item.xpath('tr/td[1]/a[5]/text()')
            url = item.xpath('tr/td[1]/a[1]/@href')
            if (len(title) > 0):
                title = title[0]
            else:
                continue
            if (len(movietime) > 0):
                movietime = movietime[0]
            else:
                movietime = ""
            if (len(country) > 0):
                country = country[0]
            else:
                country = ""
            if (len(tp) > 0):
                tp = tp[0]
            else:
                tp = ""
            if (len(url) > 0):
                url = url[0]
            else:
                url = ""
            
            dic = {'id':id,'title':title,'movietime':movietime,'country':country,'url':url,'tp':tp}
            print(dic)
            print("\n") 
            # 构建对象
            todo = self.movies()
            # 为属性赋值
            todo.set('id', dic['id'])
            todo.set('movietime', dic['movietime'])
            todo.set('type', dic['tp'])
            todo.set('country', dic['country'])
            todo.set('title', dic['title'])
            todo.set('url', dic['url'])
            # 将对象保存到云端
            todo.save()
            
             
        # 提交sql语句
        self.connect.commit()



    def createdTable(self):
        # 使用 execute() 方法执行 SQL，如果表存在则删除
        self.cursor.execute("DROP TABLE IF EXISTS MovieList")
        # 使用预处理语句创建表
        sql = """CREATE TABLE MovieList (
                id CHAR(255) NOT NULL,
                title  CHAR(255),
                movietime  CHAR(20),
                country  CHAR(20),
                url CHAR(255),
                type CHAR(20))"""
        self.cursor.execute(sql)
    

# if __name__ == '__main__':
#     movie = LCMovieListClass()
#     urls = []
#     i = 1
#     while i < 323:
#         url = "http://www.4btbtt.com/forum-index-fid-1-page-{}.htm".format(i)
#         movie.requestUrl(url)
#         urls.append(url)
#         i+=1
    # print(urls)
    # with ThreadPool(4) as pool:
    #     pool.map(movie.requestUrl, urls)


