import configparser
import os
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        # Docker Volume으로 마운트될 경로 (기본값: 로컬 경로)
        config_path = os.getenv('CONFIG_PATH', '/app/config/config.ini')
        
        self._config = configparser.ConfigParser()
        if not os.path.exists(config_path):
            logger.error(f"Config file not found at: {config_path}")
            # 필수 설정 파일이 없으면 에러를 내거나 기본값을 사용
            return

        try:
            self._config.read(config_path, encoding='utf-8')
            logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.error(f"Failed to parse config file: {e}")

    def get_section(self, section_name):
        """특정 섹션의 설정을 딕셔너리로 반환"""
        if self._config and section_name in self._config:
            # 섹션 내의 모든 키-값을 딕셔너리로 변환
            return dict(self._config[section_name])
        return {}

    def get(self, section, key, fallback=None):
        """단일 값 조회"""
        if self._config:
            return self._config.get(section, key, fallback=fallback)
        return fallback

# 전역 싱글톤 인스턴스 (어디서든 import config_loader 해서 사용)
config_loader = ConfigLoader()
