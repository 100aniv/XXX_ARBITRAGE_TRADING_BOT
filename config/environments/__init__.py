"""Environment-specific configurations"""

from config.environments.development import get_development_config as DevelopmentConfig
from config.environments.staging import get_staging_config as StagingConfig
from config.environments.production import get_production_config as ProductionConfig

__all__ = ['DevelopmentConfig', 'StagingConfig', 'ProductionConfig']
