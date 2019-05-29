import requests

requests.packages.urllib3.disable_warnings()
from datetime import datetime, timedelta, date
import time
import json
from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

config = None
with open("config.yaml", "r") as config_file:
    config = load(config_file, Loader=Loader)
    all_keys_in_config = [
        item in config and True for item in ["scanner_config"]
    ]
    if False in all_keys_in_config:
        raise ValueError("Add scanners config info in config.yaml.")

UPDATE_PROJECT_DAYS = config["scanner_config"]["update_project_days"]
UNSORTED_PRODUCT_ID = config["scanner_config"]["unsorted_product_id"]

# TODO this info should be stored in DD itself
scanners = {}
nessus = None
appscreener = None
nikto = None
if "nessus" in config["scanner_config"]:
    nessus = config["scanner_config"]["nessus"]["id"]
    scanners[nessus] = {
        "name": config["scanner_config"]["nessus"]["name"],
        "test_type_id": config["scanner_config"]["nessus"]["test_type_id"],
        "id": config["scanner_config"]["nessus"]["id_param_name"],
        "project_url": config["scanner_config"]["nessus"]["project_url"],
        "file_name": config["scanner_config"]["nessus"]["file_name"],
    }
if "appscreener" in config["scanner_config"]:
    appscreener = config["scanner_config"]["appscreener"]["id"]
    scanners[appscreener] = {
        "name": config["scanner_config"]["appscreener"]["name"],
        "test_type_id": config["scanner_config"]["appscreener"]["test_type_id"],
        "id": config["scanner_config"]["appscreener"]["id_param_name"],
        "project_url": config["scanner_config"]["appscreener"]["project_url"],
        "file_name": config["scanner_config"]["appscreener"]["file_name"],
    }
if "nikto" in config["scanner_config"]:
    nikto = config["scanner_config"]["nikto"]["id"]
    scanners[nikto] = {
        "name": config["scanner_config"]["nikto"]["name"],
        "test_type_id": config["scanner_config"]["nikto"]["test_type_id"],
        "id": config["scanner_config"]["nikto"]["id_param_name"],
        "project_url": config["scanner_config"]["nikto"]["project_url"],
        "file_name": config["scanner_config"]["nikto"]["file_name"],
    }


def get_scanner_datetime(project, scanner_key, from_engagement=False):
    last_scan_id = ""
    if scanner_key == nessus:
        if from_engagement:
            scan_time = project["info"]["scan_end"]
        else:
            scan_time = project["last_modification_date"]
    elif scanner_key == appscreener:
        if from_engagement:
            scan_time = project["dateTime"]
        else:
            scan_time = project["scan"]["dateTime"] if project["scan"] else ""
            last_scan_id = project["scan"]["uuid"]
    else:
        raise NameError(
            "Add datetime field info for {}".format(
                scanners[scanner_key]["name"]
            )
        )
    return scan_time, last_scan_id


def pretty_json(json_obj):
    return json.dumps(json_obj, indent=4, sort_keys=True)


def configure_tool(tool_configuration, project_configuration=None):
    """Configure scanner connector."""
    if tool_configuration["tool_type"] == nessus:
        scanner = Nessus(tool_configuration, project_configuration)
    elif tool_configuration["tool_type"] == appscreener:
        scanner = Appscreener(tool_configuration, project_configuration)
    elif tool_configuration["tool_type"] == nikto:
        scanner = None
    else:
        raise NameError(
            "Scanner {} is not known".format(tool_configuration["tool_type"])
        )

    return (
        scanners[tool_configuration["tool_type"]]["name"],
        scanner,
        scanners[tool_configuration["tool_type"]]["file_name"],
    )

def get_results(
    tool_config,
    project_config,
    new_item,
    last_scan_id="",
    code_dedup=False
):
    """Get scan results.

    :param tool_configuration
    :param project_configuration

    TODO set up language change in defectdojo
    """
    scan_type, scanner, file_name = configure_tool(tool_config, project_config)
    report = scanner.get_results(
        new_item=new_item,
        last_scan_id=last_scan_id,
        code_dedup=code_dedup
    )

    return {"scan_type": scan_type, "report": report, "file_name": file_name}


def get_last_projects(tool_config):
    scan_type, scanner, file_name = configure_tool(tool_config)
    if not scanner:
        return []

    return scanner.get_last_projects()


def get_project(tool_config, project_id):
    scan_type, scanner, file_name = configure_tool(tool_config)
    return scanner.get_project(project_id)

def get_new_scans(tool_config, project_config, test_update_time, tzinfo):
    scan_type, scanner, file_name = configure_tool(tool_config, project_config)
    return scanner.get_new_scans(test_update_time, tzinfo)


class Scanner(object):
    """Get scan results."""

    def __init__(self, tool_config, project_config, proxies={}):
        """Initialize scan tool."""
        self.headers = {"accept": "application/json"}
        self.proxies = proxies
        self.url = tool_config["configuration_url"] + (
            "/" if tool_config["configuration_url"][-1] != "/" else ""
        )
        if project_config:
            self.project_id = project_config["tool_project_id"]

    def _request(self, method, url, data={}, result_json=True, verify=False):
        """Senred request to Nessus."""
        req = requests.request(
            method=method,
            url=self.url + url,
            headers=self.headers,
            verify=False,
            proxies=self.proxies,
            data=data,
        )
        result = json.loads(req.text) if result_json is True else req.text
        return result

    def get_new_scans(self, test_update_time, tzinfo):
        return []



class Nessus(Scanner):
    """Get Nessus results."""

    def __init__(self, tool_configuration, project_configuration, proxies={}):
        """Initialize Nessus scanner."""
        super().__init__(
            tool_configuration, project_configuration, proxies=proxies
        )

        self.headers["X-ApiKeys"] = tool_configuration["api_key"]

    def check_status(self, file):
        """Check report status."""
        loaded = False
        counter = 0
        while not loaded:
            result = self._request(
                "GET",
                url="scans/{}/export/{}/status".format(self.project_id, file),
            )
            if result["status"] == "ready":
                loaded = True
                break
            counter += 1
            if counter > 10:
                break
            time.sleep(5)
        return loaded

    def get_results(self, new_item, last_scan_id="", code_dedup=False):
        """Get Nessus Report."""
        file_info = self._request(
            "POST",
            url="scans/{}/export".format(self.project_id),
            data={"format": "nessus"},
        )
        report = ""
        if (
            "error" in file_info
            and not file_info["error"].find("running") == -1
            and not file_info["error"].find("being exported") == -1
        ):
            return report
        loaded = self.check_status(str(file_info["file"]))
        if loaded:
            report = self._request(
                "GET",
                url="tokens/{}/download".format(file_info["token"]),
                result_json=False,
            )
        return report

    def get_last_projects(self):
        from_day = (date.today() - timedelta(UPDATE_PROJECT_DAYS)).strftime(
            "%s"
        )
        upd_projects = self._request(
            "GET", url="scans?last_modification_date={}".format(from_day)
        )
        return upd_projects["scans"] if upd_projects["scans"] else []

    def get_project(self, project_id):
        project = self._request("GET", url="scans/{}".format(project_id))
        return project


class Appscreener(Scanner):
    """Appscreener scan results."""

    def __init__(self, tool_configuration, project_configuration, proxies={}):
        """Initialize Nessus scanner."""
        super().__init__(
            tool_configuration, project_configuration, proxies=proxies
        )

        self.headers["Authorization"] = tool_configuration["api_key"]

    def get_project(self, project_id):
        """Get project from Appscreener."""

        project = self._request(
            "GET", url="projects/{}/scans/last?lang=ru".format(project_id)
        )

        return project

    def get_new_scans(self, test_update_time, tzinfo):
        super().get_new_scans(test_update_time, tzinfo)

        project_scans = self._request(
            "GET",
            url="projects/{}/scans".format(
                self.project_id
            )
        )
        print("Getting Scans List")
        new_scans = []
        for scan_info in project_scans:
            try:
                scan_time = datetime.strptime(
                scan_info['dateTime'] + tzinfo, "%Y-%m-%dT%H:%M:%SUTC%z"
                )
            except ValueError:
                scan_time = datetime.strptime(
                scan_info['dateTime'] + tzinfo, "%Y-%m-%dT%H:%MUTC%z"
                )

            print("Test update time: ",
            test_update_time,
            "; Scan update time: ",
            scan_time)

            if scan_time < test_update_time:
                break
            else:
                if scan_info['status'] == 'COMPLETE':
                    new_scans.append(scan_info['uuid'])

        return new_scans


    def get_last_projects(self):
        limit = 30
        """Update products existing in Appscreener."""
        get_more = True
        offset = 0
        projects = []
        while get_more:
            get_more = False
            current_date = datetime.now()
            upd_projects = self._request(
                "GET",
                url="projects/actual?offset={}&limit={}&sort=date&dir=asc&date=between&date_from={}&date_to={}".format(
                    offset,
                    limit,
                    (
                        current_date
                        - timedelta(days=(UPDATE_PROJECT_DAYS - 1))
                    ).strftime("%m/%d/%Y"),
                    current_date.strftime("%m/%d/%Y"),
                ),
            )
            projects = projects + upd_projects["projects"]

            if limit + offset < upd_projects["filtered"]:
                offset += limit
                get_more = True

        return projects

    def get_results(self, new_item, last_scan_id="", code_dedup=False):
        """Get Appscreener Report."""

        if not last_scan_id:
            scan = self._request(
                "GET",
                url="projects/{}/scans/last?lang=ru".format(self.project_id),
            )
            last_scan_id = scan["uuid"]

        scan_info = {}
        res = self._request("GET", url="scans/{}?lang=ru".format(last_scan_id))
        if not res["status"] == "COMPLETE":
            return []

        scan_info["dateTime"] = res["dateTime"]
        scan_info["vulns"] = self._request(
            "GET", url="scans/{}/vulnerabilities?lang=ru".format(last_scan_id)
        )
        counter = 0
        for t_ind, type in enumerate(scan_info["vulns"]):
            for i_ind, item in enumerate(type["sources"]):
                counter += 1
                path_line = item["name"].rsplit(":", 1)
                line_num = 0
                vuln_lines_count = 0
                if len(path_line) > 1:
                    lines_split = path_line[-1].rsplit("#", 1)
                    line_num = int(lines_split[0])
                    if len(lines_split) > 1:
                        vuln_lines_count = int(lines_split[1]) - line_num + 1
                    else:
                        vuln_lines_count = 1
                if new_item or not item["hasPrev"] or code_dedup:
                    full_source_code = self._request(
                        "GET",
                        url="issues/{}/source?lang=ru".format(item["uuid"]),
                    )
                    if line_num != 0:
                        lines = full_source_code["code"].splitlines()
                        begin_at = line_num - 5 if line_num > 5 else 1
                        # Select vulnerable lines plus
                        # 5 lines before and after
                        code = lines[
                            begin_at - 1 : line_num + (vuln_lines_count) + 5
                        ]
                        for l_ind, line in enumerate(code):
                            line_ending = (
                                "...[LINE WAS CUT OFF]..."
                                if len(line) > 150
                                else ""
                            )
                            if (
                                line_num
                                <= l_ind + begin_at
                                < line_num + vuln_lines_count
                            ):
                                code[l_ind] = "<{:5}.> {}".format(
                                    begin_at + l_ind, line[:150] + line_ending
                                )
                            else:
                                code[l_ind] = " {:5}.  {}".format(
                                    begin_at + l_ind, line[:150] + line_ending
                                )
                    else:
                        code = full_source_code
                    src = {
                        "code": "\n".join(code),
                        "line": line_num,
                        "count": vuln_lines_count,
                        "file": path_line[0],
                        "update_desc": True,
                    }
                    scan_info["vulns"][t_ind]["sources"][i_ind]["src"] = src
                else:
                    scan_info["vulns"][t_ind]["sources"][i_ind]["src"] = {
                        "code": "",
                        "count": vuln_lines_count,
                        "file": path_line[0],
                        "line": line_num,
                        "update_desc": False,
                    }
        return scan_info
