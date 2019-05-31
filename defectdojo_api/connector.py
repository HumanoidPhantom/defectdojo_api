import os
from defectdojo_api import defectdojo
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class Connector(object):
    """Connector to the Defect Dojo API."""

    def __init__(self, config_path):
        """Initialize connector."""
        try:
            self.proxies = {
                # 'https': 'http://127.0.0.1:8080',
                # 'http': 'http://127.0.0.1:8080'
            }
            config_import = False
            verify_ssl = True
            env_keys = ["DOJO_HOST", "DOJO_KEY2", "DOJO_KEY1", "DOJO_USER"]
            auth_data_config = ["host", "api_key", "api_key2", "user"]
            for key in env_keys:
                if key not in os.environ:
                    config_import = True


            with open(config_path, "r") as config_file:
                self.config = load(config_file, Loader=Loader)
                if "proxies" in self.config and self.config["proxies"]:
                    self.proxies = self.config["proxies"]
                if "verify_ssl" in self.config and \
                        self.config["verify_ssl"] != None:
                    verify_ssl = self.config["verify_ssl"]

                if config_import:
                    all_auth_keys_in_config = [
                        item in self.config and True
                        for item in auth_data_config
                    ]

                    if False in all_auth_keys_in_config:
                        raise ValueError(
                            "Not all required auth data is in config.yaml/env."
                            "Check if {host}, {user}, {api_key} and {api_key2}"
                            "present."
                        )
                    # instantiate the DefectDojo api wrapper
                    self.dd_v1 = defectdojo.DefectDojoAPI(
                        self.config["host"],
                        self.config["api_key"],
                        self.config["user"],
                        proxies=self.proxies,
                        verify_ssl=verify_ssl,
                    )
                    self.dd_v2 = defectdojo.DefectDojoAPI(
                        self.config["host"],
                        self.config["api_key2"],
                        self.config["user"],
                        api_version="v2",
                        proxies=self.proxies,
                        verify_ssl=verify_ssl,
                    )
                else:
                    self.dd_v1 = defectdojo.DefectDojoAPI(
                            os.environ["DOJO_HOST"],
                            os.environ["DOJO_KEY1"],
                            os.environ["DOJO_USER"],
                            proxies=self.proxies,
                            verify_ssl=verify_ssl,
                        )
                    self.dd_v2 = defectdojo.DefectDojoAPI(
                        os.environ["DOJO_HOST"],
                        os.environ["DOJO_KEY2"],
                        os.environ["DOJO_USER"],
                        api_version="v2",
                        proxies=self.proxies,
                        verify_ssl=verify_ssl,
                    )
        except FileNotFoundError as fnf_error:
            print(fnf_error)
            exit()
        except ValueError as value_error:
            print(value_error)
            exit()
