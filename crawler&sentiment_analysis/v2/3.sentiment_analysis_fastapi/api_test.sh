#!/bin/bash


echo "* Test kobert Batch Request"
echo "* Sending 3 sentences..."

curl -X POST "http://localhost:8000/predict/kobert/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "김병기 가족 베트남 방문, 대한항공과 ‘의전’ 논의 정황",
      "쿠팡 카드결제 건수 4% 급감…‘탈팡’ 심상치 않다",
      "더 만들수록 손해 美 위스키 1위 짐빔도 멈췄다… 내년 증류소 가동 중단"
    ]
  }'

echo ""
echo "* Test koelectra Batch Request"
echo "* Sending 3 sentences..."

curl -X POST "http://localhost:8000/predict/koelectra/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "김병기 가족 베트남 방문, 대한항공과 ‘의전’ 논의 정황",
      "쿠팡 카드결제 건수 4% 급감…‘탈팡’ 심상치 않다",
      "더 만들수록 손해 美 위스키 1위 짐빔도 멈췄다… 내년 증류소 가동 중단"
    ]
  }'

echo ""
echo "* Test LLM Batch Request"
echo "* Sending 3 sentences..."

curl -X POST "http://localhost:8000/predict/llm/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "김병기 가족 베트남 방문, 대한항공과 ‘의전’ 논의 정황",
      "쿠팡 카드결제 건수 4% 급감…‘탈팡’ 심상치 않다",
      "더 만들수록 손해 美 위스키 1위 짐빔도 멈췄다… 내년 증류소 가동 중단"
    ]
  }'

echo ""
echo "* Done"
