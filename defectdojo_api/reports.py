import requests
import time
import json
NESSUS = 2
APPSCREENER = 1
SCANNERS = {
    NESSUS: 'Nessus Scan',
    APPSCREENER: 'Appscreener Scan'
}


def get_results(tool_configuration, project_configuration):
    """Get scan results.

    :param tool_configuration
    :param project_configuration

    TODO set up language change in defectdojo
    """
    scan_type = ""
    report = ""
    if tool_configuration.data['tool_type'] == NESSUS:
        scan_type = SCANNERS[NESSUS]
        file_name = 'results.nessus'
        nessus = Nessus(tool_configuration, project_configuration)
        report = nessus.get_results()
    elif tool_configuration.data['tool_type'] == APPSCREENER:
        scan_type = SCANNERS[APPSCREENER]
        file_name = 'results.json'
        appscreener = Appscreener(tool_configuration, project_configuration)
        report = appscreener.get_results()
    return {
        'scan_type': scan_type,
        'report': report,
        'file_name': file_name
    }


class Scanner(object):
    """Get scan results."""

    def __init__(self, tool_config, project_config, proxies={}):
        """Initialize scan tool."""
        self.headers = {
            "accept": "application/json"
        }
        self.proxies = proxies
        self.url = tool_config.data['configuration_url'] + (
            '/' if tool_config.data['configuration_url'][-1] != '/' else ''
        )
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
        return json.loads(req.text) if result_json is True else req.text


class Nessus(Scanner):
    """Get Nessus results."""

    def __init__(self, tool_configuration, project_configuration, proxies={}):
        """Initialize Nessus scanner."""
        super().__init__(
            tool_configuration,
            project_configuration,
            proxies=proxies
        )

        self.headers["X-ApiKeys"] = tool_configuration.data['api_key']

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

    def get_results(self):
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


class Appscreener(Scanner):
    """Appscreener scan results."""

    def __init__(self, tool_configuration, project_configuration, proxies={}):
        """Initialize Nessus scanner."""
        super().__init__(
            tool_configuration,
            project_configuration,
            proxies=proxies
        )

        self.headers["Authorization"] = tool_configuration.data['api_key']

    def get_results(self):
        """Get Appscreener Report."""

        # TODO: Re-scan project: check if repo exists in incode, check if repo exists in dojo (what is priority?) if none - get old scan
        # self.headers['content-type'] = 'multipart/form-data'
        # scan = self._request(
        #     'POST',
        #     url="scan/start",
        #     data={
        #         'link': 'http://gitlab.abb-win.akbars.ru/dsa/front.git',
        #         'branch': 'dev',
        #         'uuid': self.project_id
        #     },
        #     verify=True
        # )
        #
        # print(scan)
        # exit()
        # TODO Fix with # - end of finding, not column
        scan = self._request(
            'GET',
            url="projects/{}/scans/last?lang=ru".format(self.project_id)
        )
        scan_uuid = scan['uuid']
        scan_info = self._request(
            'GET',
            url="scans/{}?lang=ru".format(scan_uuid)
        )
        scan_info['vulns'] = self._request(
            'GET',
            url="scans/{}/vulnerabilities?lang=ru".format(scan_uuid)
        )
        for t_ind, type in enumerate(scan_info['vulns']):
            for i_ind, item in enumerate(type['sources']):
                full_source_code = self._request(
                    'GET',
                    url="issues/{}/source?lang=ru".format(item['uuid'])
                )
                path_line = full_source_code['name'].rsplit(':', 1)
                line_num = 0
                vuln_lines_count = 0
                if len(path_line) > 1:
                    lines_split = path_line[-1].rsplit('#', 1)
                    line_num = int(lines_split[0])
                    if len(lines_split) > 1:
                        vuln_lines_count = int(lines_split[1]) - line_num + 1
                    else:
                        vuln_lines_count = 1
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
        return json.dumps(scan_info)
