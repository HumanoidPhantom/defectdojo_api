import os
from defectdojo_api import defectdojo
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class Connector(object):
    """Connector to the Defect Dojo API."""

    def __init__(self):
        """Initialize connector."""
        try:
            self.proxies = {
                # 'https': 'http://127.0.0.1:8080',
                # 'http': 'http://127.0.0.1:8080'
            }
            config_import = False

            env_keys = ["DOJO_HOST", "DOJO_KEY2", "DOJO_KEY1", "DOJO_USER"]
            for key in env_keys:
                if key not in os.environ:
                    config_import = True


            with open("config.yaml", "r") as config_file:
                self.config = load(config_file, Loader=Loader)
                all_keys_in_config = [
                    item in self.config and True
                    for item in ["host", "api_key", "api_key2", "user"]
                ]

                if False in all_keys_in_config:
                    raise ValueError(
                        "Not all required values in config.yaml. \
                    Check that {host}, {user}, {api_key} and {api_key2} are \
                    present."
                    )
                if config_import:
                    # instantiate the DefectDojo api wrapper
                    self.dd_v1 = defectdojo.DefectDojoAPI(
                        self.config["host"],
                        self.config["api_key"],
                        self.config["user"],
                        verify_ssl=False,
                    )
                    self.dd_v2 = defectdojo.DefectDojoAPI(
                        self.config["host"],
                        self.config["api_key2"],
                        self.config["user"],
                        api_version="v2",
                        proxies=self.proxies,
                        verify_ssl=False,
                    )
                else:
                    self.dd_v1 = defectdojo.DefectDojoAPI(
                            os.environ["DOJO_HOST"],
                            os.environ["DOJO_KEY1"],
                            os.environ["DOJO_USER"],
                            verify_ssl=False,
                        )
                    self.dd_v2 = defectdojo.DefectDojoAPI(
                        os.environ["DOJO_HOST"],
                        os.environ["DOJO_KEY2"],
                        os.environ["DOJO_USER"],
                        api_version="v2",
                        proxies=self.proxies,
                        verify_ssl=False,
                    )
        except FileNotFoundError as fnf_error:
            print(fnf_error)
            exit()
        except ValueError as value_error:
            print(value_error)
            exit()
