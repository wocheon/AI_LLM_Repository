
for i in 'kRvClpsBFJNf5du4fwAP' 'khvClpsBFJNf5du4kwC5' 'kxvClpsBFJNf5du4pgDE'
do

curl -X DELETE "http://localhost:9200/crawler_articles/_doc/$i"

done
