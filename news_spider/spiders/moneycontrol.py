import scrapy
from ..items import NewsSpiderItem  # Container Class
import re
from datetime import datetime
import string
import pandas as pd
from nsepy import get_history
from difflib import get_close_matches


class NewsSpider(scrapy.Spider):
    name = "moneycontrol"
    global excelinput
    global threshold
    global yearfrom

    threshold = pd.read_excel('input.xlsx', sheet_name='input')['THRESHOLD']
    threshold = float(threshold.dropna().tolist()[0])

    datefrom = pd.read_excel('input.xlsx', sheet_name='input')['DATEFROM']
    yearfrom = datefrom.dropna().tolist()[0].year

    excelinput = pd.read_excel('input.xlsx', sheet_name='input')['COMPANYNAME']
    excelinput = excelinput.dropna().tolist()
    excelinput = [i.upper() for i in excelinput]

    # All start URLs specified for faster access
    start_urls_a = ['https://www.moneycontrol.com/india/stockpricequote/'+i for i in string.ascii_lowercase[:27]]
    start_urls_others = ['https://www.moneycontrol.com/india/stockpricequote/others']
    start_urls = start_urls_a+start_urls_others

    def parse(self, response):
        companieslist = response.css(".MT10 .bl_12::text").extract()  # Scrape list of companies beginning w/ alphabet
        companieslist = list(map(str.upper, companieslist))  # Company names to uppercase
        companieslisturl = response.css(".MT10 .bl_12").xpath("@href").extract()  # Scrape company URLs
        companiesID1 = [i.split(sep="/")[-1] for i in companieslisturl]
        companiesID2 = [re.search("^[A-Z]*", i).group()for i in companiesID1]

        for k in excelinput:
            if len(get_close_matches(k.upper(), companieslist, cutoff=threshold)) > 0:
                closest_match = get_close_matches(k.upper(), companieslist, cutoff=threshold)[0]
                for i, j, l in zip(companieslist, companiesID1, companiesID2):
                    if closest_match == i:
                        for year in range(int(yearfrom), int(datetime.now().year)+1):
                            for pagenum in range(1, 16):
                                nexturl1 = "https://www.moneycontrol.com/stocks/company_info/stock_news.php?sc_id="+j+"&scat=&pageno="+str(pagenum)+"&next=0&durationType=Y&Year="+str(year)+"&duration=1&news_type="
                                nexturl2 = "https://www.moneycontrol.com/stocks/company_info/stock_news.php?sc_id="+l+"&scat=&pageno="+str(pagenum)+"&next=0&durationType=Y&Year="+str(year)+"&duration=1&news_type="

                                items = NewsSpiderItem()
                                items['COMPANYNAME'] = i

                                request = scrapy.Request(nexturl1, callback=self.parse_company)
                                request.meta['items'] = items
                                yield request

                                request = scrapy.Request(nexturl2, callback=self.parse_company)
                                request.meta['items'] = items
                                yield request

    def parse_company(self, response):
        items = response.meta['items']

        links = response.css(".MT15 .FL a").xpath("@href").extract()
        article_links = []
        [article_links.append("https://www.moneycontrol.com"+i) for i in links if i not in article_links]

        try:
            items['stockname'] = response.css(".gry10:nth-child(1)::text").extract()[1].strip().split()[1]
        except:
            items['stockname'] = ''

        for link in article_links:
            request = scrapy.Request(link, callback=self.parse_article)
            request.meta['items'] = items
            yield request

    def parse_article(self,response):
        items = response.meta['items']
        items['article_link'] = response.request.url

        article = response.xpath("//div[1]/section[2]/div[1]/div/article/div[3]/p").css("::text").extract()
        if article == []:
            article = response.xpath("//p").css("::text").extract()

        article = [i.replace('\n', '') for i in article]  # newline characters replaced with ''
        article = ' '.join(article)  # Convert list to string
        article = article.lower()  # convert to lower case

        words = article.split()  # Split article by whitespace into words

        # remove punctuation from each word
        table = str.maketrans('  ', '  ', string.punctuation)
        stripped = [w.translate(table) for w in words]
        article = ' '.join(stripped)

        article = article.encode(encoding='ascii', errors='ignore')  # Encoding article text in

        items['article'] = article

        title = response.css(".artTitle::text").extract()[0]
        title = title.lower()
        words = title.split()
        stripped = [w.translate(table) for w in words]
        title = ' '.join(stripped)
        items['title'] = title.encode(encoding='ascii', errors='ignore')


        dateandtime = response.css(".arttidate::text").extract()[0] # single item list of string
        dateandtime = dateandtime.split("  ")[0]        # removing "   | Source:"

        if 'Last Updated : ' in dateandtime:
            dateandtime = dateandtime.replace('Last Updated : ', '')
        if ' IST' in dateandtime:
            dateandtime = dateandtime.replace(' IST', '')

        datetime_object = datetime.strptime(dateandtime, '%b %d, %Y %I:%M %p')  # Scraped string to datetime object
        date = datetime_object.strftime("%d-%m-%Y")  # DD-MM-YY
        time = datetime_object.strftime("%H:%M")  # HH:MM

        items['date'] = date
        items['time'] = time

        try:
            stockdata = get_history(symbol=items['stockname'], start=datetime_object.date(), end=datetime_object.date())
            items['close'] = stockdata['Close'][0]
            items['prevclose'] = stockdata['Prev Close'][0]
        except:
            items['close'] = 'NA'
            items['prevclose'] = 'NA'

        items['ztemp']=''
        items['website'] = 'moneycontrol'
        yield items
