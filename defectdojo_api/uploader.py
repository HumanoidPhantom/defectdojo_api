from defectdojo_api import connector, reports, uploader
import click
from datetime import datetime, timedelta, timezone
import json
import re
import click
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

class Uploader(object):
    def __init__(self, config="config.yaml"):
        self.dc = connector.Connector(config)
        self.start_time = datetime.now()
        self.reports_configuration(config)

    def update_engagement(self, eng_id):
        """Update engagement scans."""
        engagement = self.dc.dd_v2.get_engagement(eng_id).data
        tools = self.dc.dd_v2.list_tool_products(engagement=engagement["id"])
        tests = self.dc.dd_v2.list_tests(
            engagement_id=engagement["id"]
        ).data["results"]
        for tool in tools.data["results"]:
            tool_configuration = self.dc.dd_v2.get_tool_configuration(
                tool["tool_configuration"]
            ).data
            project = reports.get_project(
                tool_config=tool_configuration, project_id=tool["tool_project_id"]
            )
            test = next(
                (item for item in tests if item["tool"] == tool["id"]), False
            )
            scan_time, last_scan_id = reports.get_scanner_datetime(
                project, tool["tool_configuration"], from_engagement=True
            )
            is_updated = self.update_project(
                engagement_id=engagement["id"],
                tool_config=tool_configuration,
                tool=tool,
                test=test,
                scan_time=scan_time,
                last_scan_id=last_scan_id,
            )

            if is_updated and engagement["target_start"] != \
            self.start_time.strftime(
                "%Y-%m-%d"
            ):
                self.dc.dd_v2.set_engagement(
                    engagement["id"],
                    target_end=(self.start_time + timedelta(weeks=1)).strftime(
                        "%Y-%m-%d"
                    ),
                )
            # TODO: add exception handling


    def update_all(self):
        for scanner_key, scanner in reports.scanners.items():
            tool_configuration = self.dc.dd_v2.get_tool_configuration(
                scanner_key
            ).data
            projects = reports.get_last_projects(tool_config=tool_configuration)
            for item in projects:
                print(item["name"])
                tools = self.dc.dd_v2.list_tool_products(
                    tool_project_id=item[scanner["id"]],
                    tool_configuration_id=tool_configuration["id"],
                ).data["results"]
                tool, engagement, test = self.get_project_data(
                    tools=tools,
                    scanner_name=item['name'],
                    tool_cfg=tool_configuration,
                    scanner=scanner,
                    project_id=item[scanner["id"]],
                )
                scan_time, last_scan_id = reports.get_scanner_datetime(
                    item, scanner_key
                )
                is_updated = self.update_project(
                    engagement_id=engagement["id"],
                    tool_config=tool_configuration,
                    tool=tool,
                    test=test,
                    scan_time=scan_time,
                    last_scan_id=last_scan_id,
                )

                if is_updated and engagement[
                    "target_start"
                ] != self.start_time.strftime("%Y-%m-%d"):

                    self.dc.dd_v2.set_engagement(
                        engagement["id"],
                        target_end=(
                            self.start_time + timedelta(weeks=1)
                        ).strftime(
                            "%Y-%m-%d"
                        ),
                    )


    def update_nikto(self, data, domain):
        """Upload Nikto scanner results.
        """
        if not reports.nikto:
            raise NameError("Add Nikto configuration in config.yaml")

        scanner = reports.scanners[reports.nikto]
        tool_configuration = self.dc.dd_v2.get_tool_configuration(
            reports.nikto
        ).data
        tools = self.dc.dd_v2.list_tool_products(
            tool_configuration_id=tool_configuration["id"],
            name=domain,
        ).data['results']

        tool, engagement, test = self.get_project_data(
            tools=tools,
            scanner_name="External Domains Nikto Scan",
            tool_cfg=tool_configuration,
            scanner=scanner,
            product_id=reports.external_product_id,
            tool_name=domain,
            type='nikto'
        )

        if not test:
            test = self.dc.dd_v2.create_test(
                engagement_id=engagement["id"],
                test_type=scanner["test_type_id"],
                environment=1,
                target_start=self.start_time.strftime("%Y-%m-%d"),
                target_end=self.start_time.strftime("%Y-%m-%d"),
            ).data

        res = self.dc.dd_v2.reupload_scan(
            test_id=test["id"],
            scan_type=scanner["name"],
            file=(scanner["file_name"], data),
            active=True,
            scan_date=self.start_time.strftime("%Y-%m-%d"),
            tool=tool["id"],
        )
        print(res)


    def engagement_delete(self, eng_id):
        self.dc.dd_v2.delete_engagement(eng_id)


    def engagement_delete_all(self):
        """Delete all products."""
        while True:
            engagements = self.dc.dd_v2.list_engagements(
                eng_type="CI/CD"
            ).data[
                "results"
            ]
            if not len(engagements):
                break
            for engagement in engagements:
                self.dc.dd_v2.delete_engagement(engagement["id"])


    def test_delete_all(self):
        """Delete all products."""
        while True:
            tests = self.dc.dd_v2.list_tests().data["results"]
            print(len(tests))
            if not len(tests):
                break
            for test in tests:
                print(test["id"])
                self.dc.dd_v2.delete_test(test["id"])


    def test_delete_findings(self, test_id):
        while True:
            findings = self.dc.dd_v2.list_findings(test=test_id).data["results"]
            if not len(findings):
                break
            for finding in findings:
                self.dc.dd_v2.delete_finding(finding["id"])


    def get_project_data(
        self,
        tools,
        scanner_name,
        tool_cfg,
        scanner,
        project_id="",
        product_id=None,
        tool_name="",
        type="",
    ):
        if not tools:
            test = False
            engagement = None
            if type == "nikto":
                engagements = self.dc.dd_v2.list_engagements(
                    product_id=product_id,
                    name=scanner_name,
                    eng_type="CI/CD",
                ).data["results"]
                if engagements:
                    engagement = engagements[0]

            if not engagement:
                engagement = self.create_engagement(
                    project=scanner_name,
                    product=product_id,
                )

            tool_base_url = tool_cfg['configuration_url'].replace(
                "/app/api/v1", ""
            )

            tool = self.dc.dd_v2.create_tool_product(
                name=tool_name if tool_name else scanner_name,
                tool_configuration=tool_cfg["id"],
                engagement=engagement["id"],
                product=engagement["product"],
                tool_project_id=project_id,
                setting_url=scanner["project_url"].format(
                    tool_base_url,
                    project_id,
                ) if project_id else "",
            ).data

        else:
            tool = tools[0]
            engagement = self.dc.dd_v2.get_engagement(tool["engagement"]).data
            tests = self.dc.dd_v2.list_tests(
                test_type=scanner["test_type_id"], tool=tool["id"]
            ).data["results"]
            test = tests[0] if tests else False

        return tool, engagement, test


    def create_engagement(self, project, product=None):
        current_user = self.dc.dd_v2.list_users(
            username=self.dc.dd_v2.user
        ).data["results"][0]["id"]

        product_id = product if product else reports.unsorted_product_id
        # TODO get info about git repository if exists
        # TODO set branch in the name
        engagement = self.dc.dd_v2.create_engagement(
            name=project,
            product_id=product_id,
            lead_id=current_user,
            status="In Progress",
            target_start=self.start_time.strftime("%Y-%m-%d"),
            target_end=(
                self.start_time + timedelta(weeks=1)
            ).strftime("%Y-%m-%d"),
        ).data

        return engagement


    def update_project(
        self,
        engagement_id,
        tool_config,
        tool,
        test,
        scan_time=None,
        last_scan_id="",
    ):
        test_update_time = None
        tzinfo = None
        if test and scan_time:
            has_update, test_update_time, tzinfo = self.check_scan_time(
                test_updated=test["updated"],
                scan_time=scan_time,
            )

            if not has_update:
                return has_update

        if tool_config["id"] == reports.appscreener \
                and test_update_time and tzinfo:
            new_scans = reports.get_new_scans(
                tool_config,
                tool,
                test_update_time,
                tzinfo
            )
        else:
            new_scans = [last_scan_id]
        success = False

        for scan_id in reversed(new_scans):
            results = reports.get_results(
                tool_config=tool_config,
                project_config=tool,
                new_item=False if test else True,
                last_scan_id=scan_id,
                code_dedup=test and "code_dedup" in test['tags']
            )

            if results["report"]:
                success = True
                if not test:
                    test = self.dc.dd_v2.create_test(
                        engagement_id=engagement_id,
                        test_type=reports.scanners[
                            tool_config["id"]
                        ]["test_type_id"],
                        environment=1,
                        target_start=self.start_time.strftime("%Y-%m-%d"),
                        target_end=self.start_time.strftime("%Y-%m-%d"),
                    ).data

                self.scan_uploader(
                    results=results,
                    tool_config_id=tool_config["id"],
                    test_id=test["id"],
                    tool_id=tool["id"],
                )
        return success


    def scan_uploader(self, results, tool_config_id, test_id, tool_id):
        limit = 20
        offset = 0
        if tool_config_id == reports.appscreener:
            amount = (
                limit
                if len(results["report"]["vulns"]) < limit
                else len(results["report"]["vulns"])
            )
        else:
            amount = limit
        while offset + limit <= amount:
            if tool_config_id == reports.appscreener:
                report = json.dumps(
                    {
                        "dateTime": results["report"]["dateTime"],
                        "vulns": results["report"]["vulns"][
                            offset : offset + limit
                        ],
                    }
                )
            else:
                report = results["report"]

            self.dc.dd_v2.reupload_scan(
                test_id=test_id,
                scan_type=results["scan_type"],
                file=(results["file_name"], report),
                active=True,
                scan_date=self.start_time.strftime("%Y-%m-%d"),
                tool=tool_id,
            ).data
            offset += limit
        print("Test {} was updated".format(test_id))


    def check_scan_time(self, test_updated, scan_time):
        test_update_time = None
        tzinfo = None
        has_update = True
        test_updated_fixed = re.sub(
            r"([-+]\d{2}):(\d{2})(?:(\d{2}))?$", r"\1\2\3", test_updated
        )
        test_updated_fixed = re.sub(
            "Z", "+0300", test_updated_fixed
        )
        test_update_time = datetime.strptime(
            test_updated_fixed, "%Y-%m-%dT%H:%M:%S.%f%z"
        )
        if type(scan_time) == int:
            scan_time = datetime.fromtimestamp(
                scan_time, test_update_time.tzinfo
            )
        elif type(scan_time) == str:
            tzinfo = re.sub(
                r"([-+]\d{2}):(\d{2})(?:(\d{2}))?$",
                r"\1\2\3",
                str(test_update_time.tzinfo),
            )
            try:
                scan_time = datetime.strptime(
                    scan_time + tzinfo, "%Y-%m-%dT%H:%M:%SUTC%z"
                )
            except ValueError:
                scan_time = datetime.strptime(
                    scan_time + tzinfo, "%Y-%m-%dT%H:%MUTC%z"
                )
        print(
            "Test update time: ",
            test_update_time,
            "; Scan update time: ",
            scan_time,
        )
        if scan_time < test_update_time:
            print("Nothing to update")
            has_update = False

        return has_update, test_update_time, tzinfo

    def reports_configuration(self, config_path):
        try:
            with open(config_path, "r") as config_file:
                config = load(config_file, Loader=Loader)
                all_keys_in_config = [
                    item in config and True for item in ["scanner_config"]
                ]
                if False in all_keys_in_config:
                    raise ValueError("Add scanners config info in config.yaml.")

            reports.update_project_days = config["scanner_config"][
                "update_project_days"
            ]
            reports.unsorted_product_id = config["scanner_config"][
                "unsorted_product_id"
            ]
            reports.external_product_id = config["scanner_config"][
                "external_domain_product_id"
            ]
            # TODO this info should be stored in DD itself
            if "nessus" in config["scanner_config"]:
                reports.nessus = config["scanner_config"]["nessus"]["id"]
                reports.scanners[reports.nessus] = {
                    "name": config["scanner_config"]["nessus"]["name"],
                    "test_type_id": config["scanner_config"]\
                        ["nessus"]["test_type_id"],
                    "id": config["scanner_config"]["nessus"]["id_param_name"],
                    "project_url": config["scanner_config"]\
                        ["nessus"]["project_url"],
                    "file_name": config["scanner_config"]["nessus"]["file_name"],
                }
            if "appscreener" in config["scanner_config"]:
                reports.appscreener = config["scanner_config"]["appscreener"]["id"]
                reports.scanners[reports.appscreener] = {
                    "name": config["scanner_config"]["appscreener"]["name"],
                    "test_type_id": config["scanner_config"]["appscreener"]\
                        ["test_type_id"],
                    "id": config["scanner_config"]["appscreener"]\
                        ["id_param_name"],
                    "project_url": config["scanner_config"]["appscreener"]\
                        ["project_url"],
                    "file_name": config["scanner_config"]["appscreener"]\
                        ["file_name"],
                }
            if "nikto" in config["scanner_config"]:
                reports.nikto = config["scanner_config"]["nikto"]["id"]
                reports.scanners[reports.nikto] = {
                    "name": config["scanner_config"]["nikto"]["name"],
                    "test_type_id": config["scanner_config"]["nikto"]\
                        ["test_type_id"],
                    "id": config["scanner_config"]["nikto"]["id_param_name"],
                    "project_url": config["scanner_config"]["nikto"]\
                        ["project_url"],
                    "file_name": config["scanner_config"]["nikto"]["file_name"],
                }
        except IOError as e:
            print('Cannot open config file {}. Error: '.format(config), e)
            exit()
