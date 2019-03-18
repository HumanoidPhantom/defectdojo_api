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
with open('config.yaml', 'r') as config_file:
    config = load(config_file, Loader=Loader)
    all_keys_in_config = [
        item in config and True
        for item in ['scanner_config']
    ]
    if False in all_keys_in_config:
        raise ValueError('Add scanners config info in config.yaml.')

UPDATE_PROJECT_DAYS = config['scanner_config']['update_project_days']
UNSORTED_PRODUCT_ID = config['scanner_config']['unsorted_product_id']
NESSUS = config['scanner_config']['nessus_id']
APPSCREENER = config['scanner_config']['appscreener_id']

# TODO this info should be stored in DD itself
SCANNERS = {
    # NESSUS: {
    #     'name': 'Nessus Scan',
    #     'test_type_id': 4,
    #     'id': 'id',
    #     'project_url': "{}/#/scans/reports/{}",
    #     'file_name': 'results.nessus'
    # },
    APPSCREENER: {
        'name': 'Appscreener Scan',
        'test_type_id': 36,
        'id': 'uuid',
        'project_url': "{}/detail/{}",
        'file_name': 'results.json'
    }
}

def get_scanner_datetime(project, scanner_key):
    last_scan_id = ""
    if scanner_key == NESSUS:
        scan_time = project['last_modification_date']
    elif scanner_key == APPSCREENER:
        scan_time = project['scan']['dateTime'] if project['scan'] else ""
        last_scan_id = project['scan']['uuid']
    else:
        raise NameError("Add datetime field info for {}".format(
            SCANNERS[scanner_key]['name'])
        )
    return scan_time, last_scan_id

def pretty_json(json_obj):
    return json.dumps(json_obj, indent=4, sort_keys=True)

def configure_tool(tool_configuration, project_configuration=None):
    """Configure scanner connector."""
    scan_type = ""
    if tool_configuration['tool_type'] == NESSUS:
        scanner = Nessus(tool_configuration, project_configuration)
    elif tool_configuration['tool_type'] == APPSCREENER:
        scanner = Appscreener(tool_configuration, project_configuration)
    else:
        raise NameError("Scanner {} does not known".format(tool_configuration['tool_type']))

    return \
        SCANNERS[tool_configuration['tool_type']]['name'], \
        scanner, \
        SCANNERS[tool_configuration['tool_type']]['file_name'] \

def get_results(tool_config, project_config, new_item, last_scan_id=""):
    """Get scan results.

    :param tool_configuration
    :param project_configuration

    TODO set up language change in defectdojo
    """
    scan_type, scanner, file_name = configure_tool(tool_config, project_config)
    report = ""
    report = scanner.get_results(new_item=new_item, last_scan_id=last_scan_id)

    return {
        'scan_type': scan_type,
        'report': report,
        'file_name': file_name
    }

def get_last_projects(tool_config):
    scan_type, scanner, file_name = configure_tool(tool_config)
    return scanner.get_last_projects()

class Scanner(object):
    """Get scan results."""

    def __init__(self, tool_config, project_config, proxies={}):
        """Initialize scan tool."""
        self.headers = {
            "accept": "application/json"
        }
        self.proxies = proxies
        self.url = tool_config['configuration_url'] + (
            '/' if tool_config['configuration_url'][-1] != '/' else ''
        )
        if project_config:
            self.project_id = project_config['tool_project_id']

    def _request(self, method, url, data={}, result_json=True, verify=False):
        """Senred request to Nessus."""
        req = requests.request(
            method=method,
            url=self.url + url,
            headers=self.headers,
            verify=False,
            proxies=self.proxies,
            data=data
        )
        result = json.loads(req.text) if result_json is True else req.text
        return result


class Nessus(Scanner):
    """Get Nessus results."""

    def __init__(self, tool_configuration, project_configuration, proxies={}):
        """Initialize Nessus scanner."""
        super().__init__(
            tool_configuration,
            project_configuration,
            proxies=proxies
        )

        self.headers["X-ApiKeys"] = tool_configuration['api_key']

    def check_status(self, file):
        """Check report status."""
        loaded = False
        counter = 0
        while not loaded:
            result = self._request(
                'GET',
                url="scans/{}/export/{}/status".format(
                    self.project_id,
                    file
                ),
            )
            if result['status'] == 'ready':
                loaded = True
                break
            counter += 1
            if counter > 10:
                break
            time.sleep(5)
        return loaded

    def get_results(self, new_item, last_scan_id=""):
        """Get Nessus Report."""
        file_info = self._request(
            'POST',
            url="scans/{}/export".format(
                self.project_id
            ),
            data={"format": "nessus"})
        loaded = self.check_status(str(file_info['file']))
        report = ""
        if loaded:
            report = self._request(
                'GET',
                url="tokens/{}/download".format(file_info['token']),
                result_json=False
            )
        return report

    def get_last_projects(self):
        from_day = (date.today() - timedelta(UPDATE_PROJECT_DAYS)).strftime("%s")
        upd_projects = self._request(
            'GET',
            url="scans?last_modification_date={}".format(
                from_day
            )
        )

        return upd_projects['scans'] if upd_projects['scans'] else []


class Appscreener(Scanner):
    """Appscreener scan results."""

    def __init__(self, tool_configuration, project_configuration, proxies={}):
        """Initialize Nessus scanner."""
        super().__init__(
            tool_configuration,
            project_configuration,
            proxies=proxies
        )

        self.headers["Authorization"] = tool_configuration['api_key']

    def get_last_projects(self):
        limit = 30
        """Update products existing in Appscreener."""

        get_more = True
        offset=0
        projects = []
        while (get_more):
            get_more = False
            current_date = datetime.now()
            upd_projects = self._request(
                'GET',
                url="projects/actual?offset={}&limit={}&sort=date&dir=desc&date=between&date_from={}&date_to={}".format(
                    offset,
                    limit,
                    (current_date - timedelta(days=(UPDATE_PROJECT_DAYS - 1))).strftime("%m/%d/%Y"),
                    current_date.strftime("%m/%d/%Y")
                ),
            )
            projects = projects + upd_projects['projects']

            if limit + offset < upd_projects['filtered']:
                offset += limit
                get_more = True

        return projects

    def get_results(self, new_item, last_scan_id=""):
        """Get Appscreener Report."""

        if not last_scan_id:
            scan = self._request(
                'GET',
                url="projects/{}/scans/last?lang=ru".format(self.project_id)
            )
            last_scan_id = scan['uuid']

        scan_info={}
        res = self._request(
            'GET',
            url="scans/{}?lang=ru".format(last_scan_id)
        )
        scan_info['dateTime'] = res['dateTime']
        scan_info['vulns'] = self._request(
            'GET',
            url="scans/{}/vulnerabilities?lang=ru".format(last_scan_id)
        )
        counter = 0
        for t_ind, type in enumerate(scan_info['vulns']):
            for i_ind, item in enumerate(type['sources']):
                counter += 1
                path_line = item['name'].rsplit(':', 1)
                line_num = 0
                vuln_lines_count = 0
                if len(path_line) > 1:
                    lines_split = path_line[-1].rsplit('#', 1)
                    line_num = int(lines_split[0])
                    if len(lines_split) > 1:
                        vuln_lines_count = int(lines_split[1]) - line_num + 1
                    else:
                        vuln_lines_count = 1

                if new_item or not item['hasPrev']:
                    full_source_code = self._request(
                        'GET',
                        url="issues/{}/source?lang=ru".format(item['uuid'])
                    )
                    if line_num != 0:
                        lines = full_source_code['code'].splitlines()
                        begin_at = line_num - 5 if line_num > 5 else 1
                        # Select vulnerable lines plus
                        # 5 lines before and after
                        code = lines[begin_at-1:line_num+(vuln_lines_count)+5]
                        for l_ind, line in enumerate(code):
                            line_ending = "...[LINE WAS CUT OFF]..." \
                                if len(line) > 150 else ""
                            if line_num <= l_ind + begin_at < line_num + \
                                    vuln_lines_count:
                                code[l_ind] = "<{:5}.> {}".format(
                                    begin_at + l_ind,
                                    line[:150] + line_ending
                                )
                            else:
                                code[l_ind] = " {:5}.  {}".format(
                                    begin_at + l_ind,
                                    line[:150] + line_ending
                                )
                    else:
                        code = full_source_code
                    src = {
                        'code': '\n'.join(code),
                        'line': line_num,
                        'count': vuln_lines_count,
                        'file': path_line[0]
                    }
                    scan_info['vulns'][t_ind]['sources'][i_ind]['src'] = src
                else:
                    scan_info['vulns'][t_ind]['sources'][i_ind]['src'] = {
                        'code': '',
                        'count': vuln_lines_count,
                        'file': path_line[0],
                        'line': line_num
                    }

        return scan_info
