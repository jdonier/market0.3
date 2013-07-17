#-*- coding: utf-8 -*-
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import redirect
import flot
from datetime import datetime
from decimal import *
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
import string, random
from operator import itemgetter
from django.db import transaction
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout 
from django.core.paginator import Paginator, EmptyPage  # Ne pas oublier l'importation
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Max, Min, Sum, Count
from markets.forms import SignupForm, LoginForm, GlobalEventForm, EventForm, MarketForm, OrderForm, TransferForm, CodeForm
from markets.models import GlobalEvent, Event, Market, Trader, Trade, Limit, OBHistory, Transfer, Code
from django.utils import simplejson
from django.utils import simplejson
from markets.getNews import *


@staff_member_required	
def unsettleEvent(request, idEvent):
	event=Event.objects.get(id=idEvent)
	event.status=0
	event.save()
	markets=Market.objects.filter(event=event)
	for market in markets:
		trades=Trade.objects.filter(market=market)
		for trade in trades:
			trade.PNL=0
			trade.save()
	return redirect(reverse(showEvent, kwargs={'idEvent':idEvent}))	

@staff_member_required	
def settleEvent(request, idEvent, idMarket):
	event=Event.objects.get(id=idEvent)
	event.status=1
	event.save()
	nbMarkets=Market.objects.filter(event=event).aggregate(Count('outcome'))['outcome__count']
	singleMarket=False
	if nbMarkets==1:
		singleMarket=True
		market=Market.objects.get(event=event)
		win=True
		if idMarket==0:
			win=False	
		market.win=win
		market.save()
		trades=Trade.objects.filter(market=market)
		for trade in trades:
			if (trade.side==1 and win==True): 
				trade.PNL=(1-trade.price)*trade.volume
			elif (trade.side==-1 and win==False):
				trade.PNL=trade.price*trade.volume
			elif (trade.side==1 and win==False):	
				trade.PNL=-trade.price*trade.volume
			elif (trade.side==-1 and win==True):	
				trade.PNL=-(1-trade.price)*trade.volume
			trade.save()	
	else:
		market=Market.objects.get(id=idMarket)
		market.win=True
		market.save()
		trades=Trade.objects.filter(market=market)
		for trade in trades:
			if trade.side==1:
				trade.PNL=(1-trade.price)*trade.volume
			else:
				trade.PNL=-(1-trade.price)*trade.volume
			trade.save()
		markets=Market.objects.filter(event=event)
		for market1 in markets:
			if market1!=market:
				market1.win=False
				market1.save()		
				trades=Trade.objects.filter(market=market1)
				for trade in trades:
					if trade.side==-1:
						trade.PNL=trade.price*trade.volume
					else:
						trade.PNL=-trade.price*trade.volume
					trade.save()
	return redirect(reverse(showEvent, kwargs={'idEvent':idEvent}))	
	

@transaction.commit_on_success	
def showMarket(request, idMarket):
	from django.db import connection
	xhr = request.GET.has_key('xhr')
	cursor = connection.cursor()
	form2 = LoginForm()
	titre="Market"
	deleted=''
	market=Market.objects.get(id=idMarket)
	event=market.event
	msgNb=0
	err=False
	settled=False
	if event.status==1:
		settled=True
		mwin='Lost'
		if market.win==True:
			mwin='Won'
	trader=Trader()
	if request.user.is_authenticated():
		trader=Trader.objects.get(user=request.user)
		idUser=trader.user.id
		if request.method == 'POST' and trader.active==True and event.status==0 and event.globalEvent.dateClose>timezone.now():
			oform = OrderForm(request.POST)
			if oform.is_valid():
				if 'buyOrder' in request.POST:
					volume=oform.cleaned_data['bvolume']
					price=oform.cleaned_data['bprice']
					side=1	
				else:
					volume=oform.cleaned_data['svolume']
					price=oform.cleaned_data['sprice']
					side=-1	
				if volume==None or price==None:
					oform.non_field_errors="Empty Fields !"
				else:	
					if Trader.objects.availableBalanceIf(trader=trader, newIdMarket=market.id, newSide=side, newPrice=price, newVolume=volume)>=0:
						try:
							deleted=execute(market, trader, side, price, volume)
							if deleted==True:
								oform.non_field_errors="Not enough balance !"	
							#else:					
							#	return redirect(reverse(showMarket, kwargs={'idMarket':idMarket, 'sd':0, 'isPost':1}))		
						except:
							oform.non_field_errors="Order not submitted"	
					else:
						oform.non_field_errors="Not enough balance !"	
		else:
			oform = OrderForm()
		deposit=float(Decimal(Trader.objects.deposit(trader=trader)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		available=float(Decimal(Trader.objects.availableBalance(trader=trader)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		risk=-float(Decimal(Trader.objects.riskEvent(trader=trader, event=market.event)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		myBuyVolume=Trade.objects.filter(Q(market=market) & ((Q(trader1=trader) & Q(side=1)) | (Q(trader2=trader) & Q(side=-1))) & Q(nullTrade=False)).aggregate(Sum('volume'))['volume__sum']		
		if myBuyVolume==None:
			myBuyVolume=0
		myBuyVolume=float(Decimal(myBuyVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))	
		mySellVolume=Trade.objects.filter(Q(market=market) & ((Q(trader1=trader) & Q(side=-1)) | (Q(trader2=trader) & Q(side=1))) & Q(nullTrade=False)).aggregate(Sum('volume'))['volume__sum']		
		if mySellVolume==None:
			mySellVolume=0
		mySellVolume=float(Decimal(mySellVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))	
		avgPriceSell=float(Decimal(Trader.objects.avgPrice(trader=trader, market=market, side=-1)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		avgPriceBuy=float(Decimal(Trader.objects.avgPrice(trader=trader, market=market, side=1)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		myBuyLimits = Limit.objects.filter(market=market, trader=trader, side=1).order_by('-timestamp')
		mySellLimits = Limit.objects.filter(market=market, trader=trader, side=-1).order_by('-timestamp')
	else:
		oform = OrderForm()	
	cursor.execute("SELECT price price, sum(volume) volume FROM markets_limit WHERE side=1 and market_id=%i GROUP BY price ORDER BY price DESC" % market.id)
	limitsBuy = dictfetchall(cursor)
	cursor.execute("SELECT price price, sum(volume) volume FROM markets_limit WHERE side=-1 and market_id=%i GROUP BY price ORDER BY price ASC" % market.id)
	limitsSell = dictfetchall(cursor)
	cursor.execute("SELECT price price, volume volume, side side, timestamp timestamp FROM markets_trade WHERE not nullTrade and market_id=%i ORDER BY timestamp DESC" % market.id)
	trades = dictfetchall(cursor)
	trades=trades[:20]
	graphData=[]
	i=0
	for trade in trades:
		trades[i]['price']=float(trades[i]['price'])
		trades[i]['volume']=float(trades[i]['volume'])
		trades[i]['timestamp']=str(trades[i]['timestamp'])
		i=i+1
	if i>0:
		price=trades[i-1]['price']	
	else:
		price=0
	i=20		
	for trade in trades:
		i=i-1	
		graphData.append([i,float(trade['price'])])#[trade['volume'], trade['price']])
	buyVolume=Limit.objects.filter(market=market, side=1).aggregate(Sum('volume'))['volume__sum']
	if buyVolume==None:
		buyVolume=0
	buyVolume=float(Decimal(buyVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))
	sellVolume=Limit.objects.filter(market=market, side=-1).aggregate(Sum('volume'))['volume__sum']
	if sellVolume==None:
		sellVolume=0
	sellVolume=float(Decimal(sellVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))
	tradedVolume=Market.objects.tradedVolume(market=market)
	if tradedVolume==None:
		tradedVolume=0
	tradedVolume=float(Decimal(tradedVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))
	openInterest=Market.objects.openInterest(market=market)
	if openInterest==None:
		openInterest=0
	openInterest=float(Decimal(openInterest).quantize(Decimal('.01'), rounding=ROUND_DOWN))
	time = str(datetime.now())	
	return render(request, 'markets/market.html', locals())

def showMarketb(request, idMarket):
	from django.db import connection
	cursor = connection.cursor()
	titre="Market"
	deleted=''
	market=Market.objects.get(id=idMarket)
	event=market.event
	settled=False
	data={}
	data['mwin']=''
	data['deposit']=''
	data['available']=''
	data['risk']=''
	data['myBuyVolume']=''
	data['mySellVolume']=''
	data['avgPriceSell']=''
	data['avgPriceBuy']=''
	data['myBuyLimits']=''
	data['mySellLimits']=''
	if event.status==1:
		settled=True
		data['mwin'] = 'Lost'
		if market.win==True:
			data['mwin'] = 'Won'
	trader=Trader()
	if request.user.is_authenticated():
		trader=Trader.objects.get(user=request.user)
		idUser=trader.user.id
		data['deposit']=float(Decimal(Trader.objects.deposit(trader=trader)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		data['available']=float(Decimal(Trader.objects.availableBalance(trader=trader)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		data['risk']=-float(Decimal(Trader.objects.riskEvent(trader=trader, event=market.event)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		myBuyVolume=Trade.objects.filter(Q(market=market) & ((Q(trader1=trader) & Q(side=1)) | (Q(trader2=trader) & Q(side=-1))) & Q(nullTrade=False)).aggregate(Sum('volume'))['volume__sum']		
		if myBuyVolume==None:
			myBuyVolume=0
		data['myBuyVolume']=float(Decimal(myBuyVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))	
		mySellVolume=Trade.objects.filter(Q(market=market) & ((Q(trader1=trader) & Q(side=-1)) | (Q(trader2=trader) & Q(side=1))) & Q(nullTrade=False)).aggregate(Sum('volume'))['volume__sum']		
		if mySellVolume==None:
			mySellVolume=0
		data['mySellVolume']=float(Decimal(mySellVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		data['avgPriceSell']=float(Decimal(Trader.objects.avgPrice(trader=trader, market=market, side=-1)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		data['avgPriceBuy']=float(Decimal(Trader.objects.avgPrice(trader=trader, market=market, side=1)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
		myBuyLimits = Limit.objects.filter(market=market, trader=trader, side=1).order_by('-timestamp')
		cursor.execute("SELECT id id, price price, volume volume FROM markets_limit WHERE side=1 and market_id=%i and trader_id=%i  ORDER BY timestamp DESC" % (market.id, trader.id))
		myBuyLimits = dictfetchall(cursor)
		mySellLimits = Limit.objects.filter(market=market, trader=trader, side=-1).order_by('-timestamp')
		cursor.execute("SELECT id id, price price, volume volume FROM markets_limit WHERE side=-1 and market_id=%i and trader_id=%i  ORDER BY timestamp DESC" % (market.id, trader.id))
		mySellLimits = dictfetchall(cursor)
		i=0
		mbl=[]
		for bl in myBuyLimits:
			mbl.append([i,float(bl['price']),float(bl['volume']), bl['id']])
		data['myBuyLimits']=mbl
		i=0
		msl=[]	
		for sl in mySellLimits:
			msl.append([i,float(sl['price']),float(sl['volume']), sl['id']])
		data['mySellLimits']=msl
	cursor.execute("SELECT id id, price price, sum(volume) volume FROM markets_limit WHERE side=1 and market_id=%i GROUP BY price ORDER BY price DESC" % market.id)
	limitsBuy = dictfetchall(cursor)
	i=0
	lbuy=[]	
	for bl in limitsBuy:
		lbuy.append([i,float(bl['price']),float(Decimal(bl['volume']).quantize(Decimal('.0001'), rounding=ROUND_DOWN)), bl['id']])
	data['limitsBuy']=lbuy
	cursor.execute("SELECT id id, price price, sum(volume) volume FROM markets_limit WHERE side=-1 and market_id=%i GROUP BY price ORDER BY price ASC" % market.id)
	limitsSell = dictfetchall(cursor)
	i=0
	lsell=[]	
	for sl in limitsSell:
		lsell.append([i,float(sl['price']),float(Decimal(sl['volume']).quantize(Decimal('.0001'), rounding=ROUND_DOWN)), sl['id']])
	data['limitsSell']=lsell
	cursor.execute("SELECT price price, volume volume, side side, timestamp timestamp FROM markets_trade WHERE not nullTrade and market_id=%i ORDER BY timestamp DESC" % market.id)
	trades = dictfetchall(cursor)
	trades=trades[:20]
	graphData=[]
	i=20
	for trade in trades:
		i=i-1	
		graphData.append([i,float(trade['price'])])#[trade['volume'], trade['price']])	
	data['graphData']=graphData	
	i=0
	for trade in trades:
		trades[i]['price']=float(trades[i]['price'])
		trades[i]['volume']=float(trades[i]['volume'])
		trades[i]['timestamp']=str(trades[i]['timestamp'])
		i=i+1	
	if i>0:
		data['price']=trades[i-1]['price']	
	else:
		data['price']=0
	buyVolume=Limit.objects.filter(market=market, side=1).aggregate(Sum('volume'))['volume__sum']
	if buyVolume==None:
		buyVolume=0
	data['buyVolume']=float(Decimal(buyVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))
	sellVolume=Limit.objects.filter(market=market, side=-1).aggregate(Sum('volume'))['volume__sum']
	if sellVolume==None:
		sellVolume=0
	data['sellVolume']=float(Decimal(sellVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))
	tradedVolume=Market.objects.tradedVolume(market=market)
	if tradedVolume==None:
		tradedVolume=0
	data['tradedVolume']=float(Decimal(tradedVolume).quantize(Decimal('.01'), rounding=ROUND_DOWN))
	openInterest=Market.objects.openInterest(market=market)
	if openInterest==None:
		openInterest=0
	data['openInterest']=float(Decimal(openInterest).quantize(Decimal('.01'), rounding=ROUND_DOWN))
	data['trades'] = trades
	data['time'] = str(datetime.now())
	json = simplejson.dumps(data)
	return HttpResponse(json, mimetype='application/json')

	
	
	
def cancelOrder(request, idLimit):
	limit=Limit.objects.get(id=idLimit)
	idMarket=limit.market.id
	limit.delete()
	return redirect(reverse(showMarket, kwargs={'idMarket':idMarket}))	

def refreshMarket(request, idMarket):
	return redirect(reverse(showMarket, kwargs={'idMarket':idMarket}))		
	
def cancelAll(request, idMarket, idUser, side):
	market=Market.objects.get(id=idMarket)
	user=User.objects.get(id=idUser)
	trader=Trader.objects.get(user=user)
	s=-1
	if int(side)==1:
		s=1
	limits=Limit.objects.filter(market=market, trader=trader,  side=s)
	for limit in limits:
		limit.delete()
	return redirect(reverse(showMarket, kwargs={'idMarket':idMarket}))
	
def showEvent(request, idEvent, page=1):	
	from django.db import connection
	cursor = connection.cursor()
	form2 = LoginForm()
	titre="Event"
	event=Event.objects.get(id=idEvent)
	markets=Market.objects.filter(event=event)
	paginator = Paginator(markets, 4)
	nbMarkets=Market.objects.filter(event=event).aggregate(Count('outcome'))['outcome__count']
	settled=(event.status==1)
	eventData=[]
	urlist=[]
	for market in markets:
		urlist.append(searchNews(str(market.outcome)))
		cursor.execute("SELECT price price, volume volume, side side, timestamp timestamp FROM markets_trade WHERE not nullTrade and market_id=%i ORDER BY timestamp DESC" % market.id)
		trades = dictfetchall(cursor)
		trades=trades[:20]
		graphData=[]
		i=20
		for trade in trades:
			i=i-1
			graphData.append([i,float(trade['price'])])#[trade['volume'], trade['price']])	
		eventData.append([market.id, graphData])
	try:
		minis = paginator.page(page)
	except EmptyPage:
		minis = paginator.page(paginator.num_pages)
	return render(request, 'markets/event.html', locals())

def showGlobalEvent(request, idgEvent, page=1):	
	form2 = LoginForm()
	titre="Event"
	gEvent=GlobalEvent.objects.get(id=idgEvent)
	events=Event.objects.filter(globalEvent=gEvent)
	paginator = Paginator(events, 4)
	try:
		minis = paginator.page(page)
	except EmptyPage:
		minis = paginator.page(paginator.num_pages)
	return render(request, 'markets/globalEvent.html', locals())

def allGlobalEvents(request, page=1):
	form2 = LoginForm()	
	titre="All Events"
	gEvents=GlobalEvent.objects.all()
	paginator = Paginator(gEvents, 4)
	try:
		minis = paginator.page(page)
	except EmptyPage:
		minis = paginator.page(paginator.num_pages)
	return render(request, 'markets/allGlobalEvents.html', locals())
	
def deleteMarket(request, idMarket):
	market=Market.objects.get(id=idMarket)
	idEvent=market.event.id	
	market.delete()
	return redirect(reverse(showEvent, kwargs={'idEvent':idEvent}))	
	
def createMarket(request, idEvent):
	form2 = LoginForm()
	title="non"
	event=Event.objects.get(id=idEvent)
	markets=Market.objects.filter(event=event)
	if request.method == "POST":
		mform = MarketForm(request.POST)
		if mform.is_valid():
			#for i in range(0, event.nbMarkets):
			market=Market()
			market.event=event
			#market.outcome = mform.cleaned_data['outcome_%i' % i]
			market.outcome = mform.cleaned_data['outcome']
			market.save()
			mform = MarketForm()	
		return render(request, 'markets/createMarket.html', locals())	
	else:
		mform = MarketForm()	
		return render(request, 'markets/createMarket.html', locals())	

def deleteEvent(request, idEvent):
	event=Event.objects.get(id=idEvent)
	idgEvent=event.globalEvent.id	
	event.delete()
	return redirect(reverse(showGlobalEvent, kwargs={'idgEvent':idgEvent}))	
	
def createEvent(request, idgEvent):
	form2 = LoginForm()
	gEvent=GlobalEvent.objects.get(id=idgEvent)
	if request.method == "POST":
		eform = EventForm(request.POST)
		if eform.is_valid():
			event=Event()
			event.globalEvent=GlobalEvent.objects.get(id=idgEvent)
			event.title = eform.cleaned_data['title']
			event.description = eform.cleaned_data['description']
			event.creator=request.user.username
			event.save()
			return HttpResponseRedirect(reverse('markets.views.createMarket', args=(event.id,)))
		else:	
			return render(request, 'markets/createEvent.html', locals())	
	else:
		eform = EventForm()	
		return render(request, 'markets/createEvent.html', locals())	

def deleteGlobalEvent(request, idgEvent):
	gEvent=GlobalEvent.objects.get(id=idgEvent)
	gEvent.delete()
	return redirect(reverse(allGlobalEvents))	
	
def createGlobalEvent(request):
	form2 = LoginForm()
	if request.method == "POST":   
		geform = GlobalEventForm(request.POST)
		if geform.is_valid():
			gEvent=GlobalEvent()
			gEvent.title = geform.cleaned_data['title']
			gEvent.dateClose = geform.cleaned_data['dateClose']
			gEvent.save()
			return HttpResponseRedirect(reverse('markets.views.createEvent', args=(gEvent.id,)))	
		else:	
			return render(request, 'markets/createGlobalEvent.html', locals())	
	else:
		geform = GlobalEventForm()	
		return render(request, 'markets/createGlobalEvent.html', locals())	

def allTraders(request, page=1):
	form2 = LoginForm()	
	traders=Trader.objects.all()
	paginator = Paginator(traders, 10)
	try:
		minis = paginator.page(page)
	except EmptyPage:
		minis = paginator.page(paginator.num_pages)
	return render(request, 'markets/allTraders.html', locals())
	
@staff_member_required
def toggleActivateTrader(request, idUser):	
	user=User.objects.get(id=idUser)
	trader=Trader.objects.get(user=user)
	trader.active= not trader.active
	trader.save()
	return redirect(reverse(showTrader, kwargs={'idUser':idUser}))	
	
@login_required	
def showTrader(request, idUser):	
	user=User.objects.get(id=idUser)
	trader=Trader.objects.get(user=user)
	titre=u'{0}'.format(user.username)
	if trader.active:
		action='Deactivate'
	else:
		action='Activate'
	return render(request, 'markets/trader.html', locals())	
	
def signup(request):
	if request.method == "POST":   
		form = SignupForm(request.POST)
		if form.is_valid():
			try:
				code = Code.objects.get(code=form.cleaned_data['code'])
			except:
				code=''
			if code!='':
				if code.active==True:
					code.active=False
					code.save()
					user=User()
					user.username = form.cleaned_data['username']
					user.email = form.cleaned_data['email']
					user.set_password(form.cleaned_data['password'])
					user.save()
					trader=Trader(user=user)
					trader.save()
					transfer=Transfer()
					transfer.trader=trader
					transfer.type=1
					transfer.volume=100
					transfer.save()			
					user = authenticate(username=form.cleaned_data['username'], password=form.cleaned_data['password'])  #Nous vérifions si les données sont correctes
					login(request, user)
					#return redirect('posts.views.user', id_user=user.id)
					return redirect('markets.views.home')
				else:
					form.non_field_errors="Wrong code"
					form2 = LoginForm()
			else:
				form.non_field_errors="Wrong code"
				form2 = LoginForm()
	else:
		form2 = LoginForm()
		form = SignupForm()	
	return render(request, 'markets/signup.html', locals())	

def signin(request):
	error = False    
	form = LoginForm(request.POST)
	if form.is_valid():
		username = form.cleaned_data["username"]  # Nous récupérons le nom d'utilisateur
		password = form.cleaned_data["password"]  # … et le mot de passe
		user = authenticate(username=username, password=password)  #Nous vérifions si les données sont correctes
		if user:  # Si l'objet renvoyé n'est pas None
			login(request, user)  # nous connectons l'utilisateur
			if not Trader.objects.filter(user=user):
				trader=Trader(user=user)
				trader.save()
		else: #sinon une erreur sera affichée
			error = True
	return redirect('markets.views.home')

def home(request):		
	from django.db import connection
	cursor = connection.cursor()
	titre="Home"
	form2 = LoginForm()
	if request.method == "POST" and request.user.is_authenticated():   
		trform = TransferForm(request.POST)
		if trform.is_valid():
			transfer=Transfer()
			transfer.trader=Trader.objects.get(user=request.user)
			transfer.type=trform.cleaned_data["type"]
			transfer.volume=trform.cleaned_data["volume"]
			transfer.save()			
			trform = TransferForm()	
			trform.non_field_errors="Transfer successful !"
		else:	
			trform = TransferForm()	
	else:	
		trform = TransferForm()
	marketPerf=[]
	for market in Market.objects.all():
		if market.event.status==0 and market.event.globalEvent.dateClose>timezone.now():
			tv=Market.objects.tradedVolume(market=market)			
			if tv==None:
				tv=0
			tv=float(Decimal(tv).quantize(Decimal('.01'), rounding=ROUND_DOWN))	
			marketPerf.append([market.id, tv])
	marketPerf.sort(key=lambda k: (k[1]), reverse=True)
	marketPerf=marketPerf[0:3]
	perfData=[]
	perfName=[]
	for mp in range(0,3):
		market=Market.objects.get(id=marketPerf[mp][0])
		marketId=marketPerf[mp][0]
		cursor.execute("SELECT price price, volume volume, side side, timestamp timestamp FROM markets_trade WHERE not nullTrade and market_id=%i ORDER BY timestamp DESC" % marketId)
		trades = dictfetchall(cursor)
		trades=trades[:20]
		graphData=[]
		i=20
		for trade in trades:
			i=i-1
			graphData.append([i,float(trade['price'])])#[trade['volume'], trade['price']])	
		perfData.append([mp, graphData])
		if mp==0:
			n0=market.outcome	
			id0=market.id		
		if mp==1:
			n1=market.outcome
			id1=market.id				
		if mp==2:
			n2=market.outcome
			id2=market.id				
	return render(request, 'markets/home.html', locals())
	
def createCodes(request):
	titre="Codes"
	form2 = LoginForm()
	if request.method == "POST" and request.user.is_superuser:   
		cdform = CodeForm(request.POST)
		if cdform.is_valid():
			nbCodes=cdform.cleaned_data["nbCodes"]
			for i in range(nbCodes):
				code=''.join(random.choice(string.ascii_lowercase + string.digits) for x in range(10))
				newCode=Code(code=code)
				newCode.save()	
			cdform = CodeForm()	
			cdform.non_field_errors="%d codes created !" % nbCodes
		else:	
			cdform = CodeForm()	
	else:
		cdform = CodeForm()	
	codes=Code.objects.filter(active=True)		
	return render(request, 'markets/createCodes.html', locals())	


def contact(request):
	titre="Contact"
	form2 = LoginForm()
	return render(request, 'markets/contact.html', locals())	
	
	
def help(request):
	titre="Help"
	form2 = LoginForm()
	return render(request, 'markets/help.html', locals())	
	
def about(request):
	titre="About"
	form2 = LoginForm()
	return render(request, 'markets/about.html', locals())	


def signout(request):
	logout(request)
	return redirect('markets.views.home')


	
	
	
	
#Other functions	

def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

def execute(market, trader, side, price, volume):
	volToExec=volume
	while side==1 and volToExec>0	and Limit.objects.filter(market=market, side=-1).aggregate(Min('price'))["price__min"]!=None and Limit.objects.filter(market=market, side=-1).aggregate(Min('price'))["price__min"]<=price:
		priceMin=Limit.objects.filter(market=market, side=-1).aggregate(Min('price'))["price__min"]
		timestampMin=Limit.objects.filter(market=market, price=priceMin, side=-1).aggregate(Min('timestamp'))["timestamp__min"]
		order=Limit.objects.get(market=market, price=priceMin, timestamp=timestampMin, side=-1)
		if order.volume<=volToExec:
			trade=Trade(market=market, trader1=trader, trader2=order.trader, side=1, price=order.price, volume=order.volume, nullTrade=(trader==order.trader)) 
			volInt=order.volume
			volToExec-=volInt
			trade.save()
			if Trader.objects.availableBalance(trader=trader)>=0:
				order.delete();
			else:	
				trade.delete()
		else:
			trade=Trade(market=market, trader1=trader, trader2=order.trader, side=1, price=order.price, volume=volToExec, nullTrade=(trader==order.trader)) 
			order.volume-=volToExec	
			volToExec=0
			trade.save()
			if Trader.objects.availableBalance(trader=trader)>=0:
				order.save();
			else:	
				trade.delete()
			
	while side==-1 and volToExec>0 and Limit.objects.filter(market=market, side=1).aggregate(Max('price'))["price__max"]!=None and Limit.objects.filter(market=market, side=1).aggregate(Max('price'))["price__max"]>=price:
		priceMax=Limit.objects.filter(market=market, side=1).aggregate(Max('price'))["price__max"]
		timestampMin=Limit.objects.filter(market=market, price=priceMax, side=1).aggregate(Min('timestamp'))["timestamp__min"]
		order=Limit.objects.get(market=market, price=priceMax, timestamp=timestampMin, side=1)	
		if order.volume<=volToExec:
			trade=Trade(market=market, trader1=trader, trader2=order.trader, side=-1, price=order.price, volume=order.volume, nullTrade=(trader==order.trader))
			volInt=order.volume
			volToExec-=volInt
			trade.save()
			if Trader.objects.availableBalance(trader=trader)>=0:
				order.delete();
			else:	
				trade.delete()
		else:
			trade=Trade(market=market, trader1=trader, trader2=order.trader, side=-1, price=order.price, volume=volToExec, nullTrade=(trader==order.trader)) 
			order.volume-=volToExec	
			order.save()		
			volToExec=0
			trade.save()
			if Trader.objects.availableBalance(trader=trader)>=0:
				order.save();
			else:	
				trade.delete()
			
	#Crée un limit order sur ce qui reste	
	deleted=False
	if volToExec>0:
		limit=Limit(market=market, trader=trader, side=side, price=price, volume=volToExec)
		limit.save()
		if Trader.objects.availableBalance(trader=trader)<0:
			limit.delete()
			deleted=True
	return deleted