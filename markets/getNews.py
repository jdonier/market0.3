import urllib, urllib2,string,sys,urlparse,time,os,random
from urllib2 import URLError, HTTPError
from sgmllib import SGMLParser


#user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
#values = {'name' : 'Michael Foord',
#          'location' : 'Northampton',
#          'language' : 'Python' }
#theaders = { 'User-Agent' : user_agent }
#
#tdata = urllib.urlencode(values)

#if not os.path.exists(BaseFolder+'-'+str(currday)+'-'+str(currmonth)+'-'+str(curryear)+'\\'):
#    os.makedirs(BaseFolder+'-'+str(currday)+'-'+str(currmonth)+'-'+str(curryear)+'\\')    

#searchword='yahoo'

class URLLister(SGMLParser):
    def reset(self):                              
        SGMLParser.reset(self)
        self.urls = []

    def start_a(self, attrs):                     
        href = [v for k, v in attrs if k=='href'] 
        if href:
            self.urls.extend(href)

def list_urls(searchterm,newservers):
	txdata = None
	txheaders = {}
	txheaders['User-Agent']='Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
	txheaders['Keep-Alive']='300'
	txheaders['Connection']='keep-alive'
	txheaders['Cache-Control']='max-age=0'
	#url = 'http://news.google.com/news?as_q='+searchterm+'&svnum=10&as_scoring=d&hl=en&ned=&btnG=Google+Search&as_epq=&as_oq=&as_eq=&as_nsrc='+source+'&as_nloc=&as_occt=any&as_drrb=q&as_qdr=d&as_mind=29&as_minm=3&as_maxd=28&as_maxm=4'
	url='https://www.google.com/search?hl=en&gl=us&tbm=nws&authuser=0&q='+searchterm+'&oq='+searchterm+'&gs_l=news-cc.3.0.43j0j43i53.16455.24274.0.26206.13.4.3.6.8.0.75.283.4.4.0...0.0...1ac.1.5xkwBVolcU8'
	req = urllib2.Request(url, txdata, txheaders)
#    req = urllib2.Request(url)#, tdata, theaders)
	u = urllib2.urlopen(req)
#    headers = u.info()
#    print headers
	data = u.read()
	u.close()
	parser = URLLister()
	parser.feed(data)
	parser.close()
	urlist=[]
	for url in parser.urls:
		for newserver in newservers:
			if string.find(url,newserver)>=0:
				if string.find(url,"news.google.com")<0:
					urlist.append(url[7:url.index('&')])
	return urlist

def searchNews(swd):
	# Main parameters
	#BaseFolder='C:\\Workarea\\Dev\\Scripts\\Reuters\\data\\'
	BaseFolder='D:\Jonathan\X\EA\News'

	# swd=r'D:\Jonathan\X\EA\searchwords.txt'

	# #open searchwords
	# sw=open(swd,'r')
	# searchwords=sw.readlines()
	# sw.close()

	# Some definitions
	counter=1
	curryear=str(time.localtime()[0])
	currmonth=str(time.localtime()[1])
	currday=str(time.localtime()[2])
		
	txdata = None
	txheaders = {}
	txheaders['User-Agent']='Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
	txheaders['Keep-Alive']='300'
	txheaders['Connection']='keep-alive'
	txheaders['Cache-Control']='max-age=0'
	searchwords=[]
	searchwords.append(swd)
	for searchword in searchwords:
		urlist=list_urls(searchword,['usatoday.com', 'foxnews.com','reuters.com','bloomberg.com'])
		return urlist
