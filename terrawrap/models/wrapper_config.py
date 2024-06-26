"""Data classes to represent the wrapper config file"""
# TODO: convert these classes to dataclasses once we drop support for Python3.6
# pylint: disable=missing-docstring

from enum import Enum
from typing import Dict, Optional, List

import jsons


class EnvVarSource(Enum):
    SSM = 'ssm'
    TEXT = 'text'
    UNSET = 'unset'


class AbstractEnvVarConfig:
    def __init__(self, source: EnvVarSource):
        self.source = source


class SSMEnvVarConfig(AbstractEnvVarConfig):
    def __init__(self, path: str):
        super().__init__(EnvVarSource.SSM)
        self.path = path


class TextEnvVarConfig(AbstractEnvVarConfig):
    def __init__(self, value: str):
        super().__init__(EnvVarSource.TEXT)
        self.value = value


class UnsetEnvVarConfig(AbstractEnvVarConfig):
    def __init__(self):
        super().__init__(EnvVarSource.UNSET)


class HTTPBackendConfig:
    def __init(
            self,
            address: str = None,
            update_method: str = None,
            lock_address: str = None,
            lock_method: str = None,
            unlock_address: str = None,
            unlock_method: str = None,
            username: str = None,
            password: str = None,
            skip_cert_verification: str = None,
            retry_max: str = None,
            retry_wait_min: str = None,
            retry_wait_max: str = None,
    ):
        self.address = address
        self.update_method = update_method
        self.lock_address = lock_address
        self.lock_method = lock_method
        self.unlock_address = unlock_address
        self.unlock_method = unlock_method
        self.username = username
        self.password = password
        self.skip_cert_verifications = skip_cert_verification
        self.retry_max = retry_max
        self.retry_wait_min = retry_wait_min
        self.retry_wait_max = retry_wait_max


class S3BackendConfig:
    def __init__(
            self,
            bucket: str = None,
            region: str = None,
            dynamodb_table: str = None,
            role_arn: str = None,
    ):
        self.region = region
        self.bucket = bucket
        self.dynamodb_table = dynamodb_table
        self.role_arn = role_arn


class GCSBackendConfig:
    def __init__(self, bucket: str = None):
        self.bucket = bucket


class BackendsConfig:
    # pylint: disable=invalid-name
    def __init__(self, s3: Optional[S3BackendConfig] = None, gcs: Optional[GCSBackendConfig] = None, http: Optional[HTTPBackendConfig] = None):
        self.http = http
        self.s3 = s3
        self.gcs = gcs


# pylint: disable=unused-argument
def env_var_deserializer(obj_dict, cls, **kwargs):
    """convert a dict to a subclass of AbstractEnvVarConfig"""
    if obj_dict['source'] == EnvVarSource.SSM.value:
        return SSMEnvVarConfig(obj_dict['path'])
    if obj_dict['source'] == EnvVarSource.TEXT.value:
        return TextEnvVarConfig(obj_dict['value'])
    if obj_dict['source'] == EnvVarSource.UNSET.value:
        return UnsetEnvVarConfig()

    raise RuntimeError('Invalid Source')


jsons.set_deserializer(env_var_deserializer, AbstractEnvVarConfig)


# pylint: disable=too-many-arguments
class WrapperConfig:
    def __init__(
            self,
            configure_backend: bool = True,
            pipeline_check: bool = True,
            backend_check: bool = True,
            plan_check: bool = True,
            envvars: Dict[str, AbstractEnvVarConfig] = None,
            backends: BackendsConfig = None,
            depends_on: List[str] = None,
            config: bool = True,
            audit_api_url: str = None,
            apply_automatically: bool = True,
            plugins: Dict[str, str] = None
    ):
        self.configure_backend = configure_backend
        self.pipeline_check = pipeline_check
        self.backend_check = backend_check
        self.plan_check = plan_check
        self.envvars = envvars or {}
        self.backends = backends
        self.depends_on = depends_on
        self.config = config
        self.audit_api_url = audit_api_url
        self.apply_automatically = apply_automatically
        self.plugins = plugins or {}
