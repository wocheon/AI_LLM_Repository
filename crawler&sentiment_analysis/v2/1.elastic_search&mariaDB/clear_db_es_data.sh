# delete ES data
echo "### DELETE ES DATA###"
curl -X DELETE "http://localhost:9200/crawler_articles" | jq .
echo ""
curl -X DELETE "http://localhost:9200/article_summary" | jq

# delete mysql data
echo "### DELETE SQL DATA###"
mysql -h 127.0.0.1 -P 3306 -u root -prootpass << EOF 
truncate table crawler_sentiment_analysis.crawler_article_list ;
truncate table crawler_sentiment_analysis.sentiment_results ;
select 'crawler_article_list' as table_name,  count(*) from crawler_sentiment_analysis.crawler_article_list
union all
select 'sentiment_results' as table_name, count(*) from crawler_sentiment_analysis.sentiment_results;
EOF
