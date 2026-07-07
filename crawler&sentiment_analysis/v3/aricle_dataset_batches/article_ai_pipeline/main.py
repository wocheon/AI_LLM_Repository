import argparse
import asyncio
import sys
import os
import time

# [커스텀 모듈 임포트]
from src.common.config import load_config
from src.common.logger import setup_logger

# [비즈니스 로직 모듈 임포트]
from src.jobs import summarizer
from src.jobs import labeler
from src.jobs import embedder

# 메인 로거 설정 (화면 출력용)
logger = setup_logger("Main", None)  # 파일 저장은 안 하고 콘솔 출력만

async def main():
    # 1. Argument Parser 설정
    parser = argparse.ArgumentParser(
        description="News Refinery: AI-based News Data Processing Pipeline",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        'mode', 
        choices=['summary', 'label', 'embed', 'all'], 
        help=(
            "실행할 작업 모드 선택:\n"
            "  summary : LLM 요약 생성\n"
            "  label   : 감성 분석 및 타겟 추출\n"
            "  embed   : 벡터 임베딩 생성\n"
            "  all     : 위 3단계 순차 실행 (파이프라인)"
        )
    )
    
    parser.add_argument(
        '--id', 
        type=int, 
        default=None, 
        help="특정 DB ID만 지정해서 처리 (누락 데이터 수동 처리용)"
    )
    
    parser.add_argument(
        '--config', 
        type=str, 
        default='config.ini', 
        help="설정 파일 경로 (기본값: config.ini)"
    )

    args = parser.parse_args()

    # 2. Config 로드
    logger.info(f"📂 설정 파일 로드 중... ({args.config})")
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"설정 파일 로드 실패: {e}")
        sys.exit(1)

    # 3. 실행 정보 출력
    target_msg = f"Target ID: {args.id}" if args.id else "Target: BATCH Processing"
    logger.info(f"🚀 실행 모드: [{args.mode.upper()}] | {target_msg}")

    # 4. 작업 라우팅 (Job Routing)
    start_time = time.time()
    
    try:
        if args.mode == 'summary':
            await summarizer.run(config, target_id=args.id)
            
        elif args.mode == 'label':
            await labeler.run(config, target_id=args.id)
            
        elif args.mode == 'embed':
            await embedder.run(config, target_id=args.id)
            
        elif args.mode == 'all':
            logger.info("============== [Step 1] 요약(Summary) 시작 ==============")
            await summarizer.run(config, target_id=args.id)
            
            logger.info("============== [Step 2] 라벨링(Labeling) 시작 ==============")
            await labeler.run(config, target_id=args.id)
            
            logger.info("============== [Step 3] 임베딩(Embedding) 시작 ==============")
            await embedder.run(config, target_id=args.id)

    except KeyboardInterrupt:
        logger.warning("\n🛑 사용자에 의해 작업이 강제 중단되었습니다.")
    except Exception as e:
        logger.error(f"❌ 작업 중 예기치 못한 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        elapsed = time.time() - start_time
        logger.info(f"🏁 전체 프로세스 종료 (총 소요시간: {elapsed:.2f}초)")

if __name__ == "__main__":
    # Windows 환경에서 asyncio RuntimeError 방지
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
