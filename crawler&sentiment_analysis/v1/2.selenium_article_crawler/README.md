# 기사 수집용 Crawler (Google RSS 사용)

## 동작 방식 
1. google RSS를 통해 키워드 별 기사 검색 
    - 수집 기사는 키워드별 5개로 제한해둔 상태
2. 기사 본문 수집을 위해 수집된 기사의 원문 주소를 추출 
    - Selenium을 통해 Google RSS로 받아온 기사 주소를 Chrome 브라우저에서 실행
    - Google RSS 주소를 웹브라우저에서 접근하면 원문 기사 주소로 Rediect
    - 다음 기사로 넘어갈 때마다 새로운 탭을 열고 다음 기사로 넘어갈때 닫는 방식으로 진행
3. requests+BeautifulSoup, newspaper3k 로 기사 본문을 추출 
    - 두 방식으로 불가한 경우, selenium을 통해 기사 본문 추출 진행
4. 키워드 별 기사 정보 및 기사 본문 저장
    - 키워드 별 수집된 기사 정보는 mysqlDB에 기록
    - 기사 본문은 elasticsearch에 문서로 저장 


## Docker 이미지 빌드 & 실행 

### Docker image Build 
```
docker image prune -f
docker build --rm -t selenium_crawler_test .
```

## Docker Run Container

```
docker run -d --network=host  \
	-v ./log:/app/log \
	--name selenium_crawler_test selenium_crawler_test:latest
```


## 결과 조회

```
select * from crawler_sentiment_analysis.crawler_article_list;
```


```
curl -X GET "http://localhost:9200/test-index/_doc/1"
```