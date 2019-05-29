from defectdojo_api import connector, reports, uploader
import click
from datetime import datetime, timedelta, timezone
import json
import re


def update_engagement(eng_id):
    """Update engagement scans."""
    dc = connector.Connector()
    engagement = dc.dd_v2.get_engagement(eng_id).data
    start_time = datetime.now()

    tools = dc.dd_v2.list_tool_products(engagement=engagement["id"])
    tests = dc.dd_v2.list_tests(engagement_id=engagement["id"]).data["results"]
    for tool in tools.data["results"]:
        tool_configuration = dc.dd_v2.get_tool_configuration(
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
        is_updated = update_project(
            dc=dc,
            engagement_id=engagement["id"],
            tool_config=tool_configuration,
            tool=tool,
            test=test,
            start_time=start_time,
            scan_time=scan_time,
            last_scan_id=last_scan_id,
        )

        if is_updated and engagement["target_start"] != start_time.strftime(
            "%Y-%m-%d"
        ):
            dc.dd_v2.set_engagement(
                engagement["id"],
                target_end=(start_time + timedelta(weeks=1)).strftime(
                    "%Y-%m-%d"
                ),
            )
        # TODO: add exception handling


def update_all():
    dc = connector.Connector()
    start_time = datetime.now()
    for scanner_key, scanner in reports.scanners.items():
        tool_configuration = dc.dd_v2.get_tool_configuration(scanner_key).data
        projects = reports.get_last_projects(tool_config=tool_configuration)
        for item in projects:
            print(item["name"])
            tools = dc.dd_v2.list_tool_products(
                tool_project_id=item[scanner["id"]],
                tool_configuration_id=tool_configuration["tool_type"],
            ).data["results"]

            tool, engagement, test = get_project_data(
                dc=dc,
                tools=tools,
                scanner_name=item['name'],
                tool_cfg=tool_configuration,
                scanner=scanner,
                start_time=start_time,
                project_id=item[scanner["id"]],
            )

            scan_time, last_scan_id = reports.get_scanner_datetime(
                item, scanner_key
            )
            is_updated = update_project(
                dc=dc,
                engagement_id=engagement["id"],
                tool_config=tool_configuration,
                tool=tool,
                test=test,
                start_time=start_time,
                scan_time=scan_time,
                last_scan_id=last_scan_id,
            )

            if is_updated and engagement[
                "target_start"
            ] != start_time.strftime("%Y-%m-%d"):

                dc.dd_v2.set_engagement(
                    engagement["id"],
                    target_end=(start_time + timedelta(weeks=1)).strftime(
                        "%Y-%m-%d"
                    ),
                )


def scan_nikto(data):
    """Load engagements.

    Start Nikto scanner and get data.
    """
    start_time = datetime.now()
    dc = connector.Connector()
    if not reports.nikto:
        raise NameError("Add Nikto configuration in config.yaml")

    scanner = reports.scanners[reports.nikto]
    tool_configuration = dc.dd_v2.get_tool_configuration(reports.nikto).data
    tools = dc.dd_v2.list_tool_products(
        tool_configuration_id=tool_configuration["tool_type"],
    ).data['results']

    tool, engagement, test = get_project_data(
        dc=dc,
        tools=tools,
        scanner_name="External Domains Nikto Scan",
        tool_cfg=tool_configuration,
        scanner=scanner,
        start_time=start_time,
    )

    if not test:
        test = dc.dd_v2.create_test(
            engagement_id=engagement["id"],
            test_type=scanner["test_type_id"],
            environment=1,
            target_start=start_time.strftime("%Y-%m-%d"),
            target_end=start_time.strftime("%Y-%m-%d"),
        ).data

    res = dc.dd_v2.reupload_scan(
        test_id=test["id"],
        scan_type=scanner["name"],
        file=(scanner["file_name"], data),
        active=True,
        scan_date=start_time.strftime("%Y-%m-%d"),
        tool=tool["id"],
    )

    print(res)


def engagement_delete_all():
    """Delete all products."""
    dc = connector.Connector()
    while True:
        engagements = dc.dd_v2.list_engagements(eng_type="CI/CD").data[
            "results"
        ]
        if not len(engagements):
            break
        for engagement in engagements:
            dc.dd_v2.delete_engagement(engagement["id"])


def test_delete_all():
    """Delete all products."""
    dc = connector.Connector()
    while True:
        tests = dc.dd_v2.list_tests().data["results"]
        print(len(tests))
        if not len(tests):
            break
        for test in tests:
            print(test["id"])
            dc.dd_v2.delete_test(test["id"])


def test_delete_findings(test_id):
    dc = connector.Connector()
    while True:
        findings = dc.dd_v2.list_findings(test=test_id).data["results"]
        if not len(findings):
            break
        for finding in findings:
            dc.dd_v2.delete_finding(finding["id"])


def get_project_data(
    dc,
    tools,
    scanner_name,
    tool_cfg,
    scanner,
    start_time,
    project_id="",
):
    if not tools:
        test = False
        engagement = create_engagement(
            dc=dc, project=scanner_name, start_time=start_time
        )

        tool_base_url = tool_cfg['configuration_url'].replace("/app/api/v1", "")

        tool = dc.dd_v2.create_tool_product(
            name="{}".format(scanner_name),
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
        engagement = dc.dd_v2.get_engagement(tool["engagement"]).data
        tests = dc.dd_v2.list_tests(
            test_type=scanner["test_type_id"], tool=tool["id"]
        ).data["results"]
        test = tests[0] if tests else False

    return tool, engagement, test


def create_engagement(dc, project, start_time, product=None):
    current_user = dc.dd_v2.list_users(username=dc.dd_v2.user).data["results"][
        0
    ]["id"]

    product_id = product if product else reports.UNSORTED_PRODUCT_ID
    # TODO get info about git repository if exists
    # TODO set branch in the name
    engagement = dc.dd_v2.create_engagement(
        name=project,
        product_id=product_id,
        lead_id=current_user,
        status="In Progress",
        target_start=start_time.strftime("%Y-%m-%d"),
        target_end=(start_time + timedelta(weeks=1)).strftime("%Y-%m-%d"),
    ).data

    return engagement


def update_project(
    dc,
    engagement_id,
    tool_config,
    tool,
    test,
    start_time,
    scan_time=None,
    last_scan_id="",
):
    test_update_time = None
    tzinfo = None
    if test and scan_time:
        has_update, test_update_time, tzinfo = check_scan_time(
            test_updated=test["updated"],
            scan_time=scan_time,
        )

        if not has_update:
            return has_update

    if tool_config["tool_type"] == reports.appscreener \
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
                test = dc.dd_v2.create_test(
                    engagement_id=engagement_id,
                    test_type=reports.scanners[
                        tool_config["id"]
                    ]["test_type_id"],
                    environment=1,
                    target_start=start_time.strftime("%Y-%m-%d"),
                    target_end=start_time.strftime("%Y-%m-%d"),
                ).data

            scan_uploader(
                dc=dc,
                results=results,
                tool_type=tool_config["tool_type"],
                test_id=test["id"],
                tool_id=tool["id"],
                start_time=start_time,
            )
    return success


def scan_uploader(dc, results, tool_type, test_id, tool_id, start_time):
    limit = 20
    offset = 0
    if tool_type == reports.appscreener:
        amount = (
            limit
            if len(results["report"]["vulns"]) < limit
            else len(results["report"]["vulns"])
        )
    else:
        amount = limit
    while offset + limit <= amount:
        if tool_type == reports.appscreener:
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

        dc.dd_v2.reupload_scan(
            test_id=test_id,
            scan_type=results["scan_type"],
            file=(results["file_name"], report),
            active=True,
            scan_date=start_time.strftime("%Y-%m-%d"),
            tool=tool_id,
        ).data
        offset += limit
    print("Test {} was updated".format(test_id))


def check_scan_time(test_updated, scan_time):
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
