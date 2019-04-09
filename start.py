from defectdojo_api import connector, reports
import click
from datetime import datetime, timedelta, timezone
import json
import re


@click.group()
def main():
    """CLI for Defect Dojo."""
    pass


@main.command()
def update_scans():
    """Update all product scans."""
    dc = connector.Connector()
    products = dc.dd_v2.list_products()
    for product in products.data["results"]:
        engagements = dc.dd_v2.list_engagements(
            product_id=product["id"], eng_type="CI/CD"
        )
        # TODO: Add field that would connect Engagemnt Test and Product Tool
        # TODO: lead_id - who is lead?
        start_time = datetime.now()
        for engagement in engagements.data["results"]:
            tests = dc.dd_v2.list_tests(engagement_id=engagement["id"]).data[
                "results"
            ]
            dc.dd_v2.set_engagement(
                engagement["id"],
                target_end=(start_time + timedelta(weeks=1)).strftime(
                    "%Y-%m-%d"
                ),
            )
            tools = dc.dd_v2.list_tool_products(
                product_id=product["id"], description=engagement["name"]
            )

            for tool in tools.data["results"]:
                tool_configuration = dc.dd_v2.get_tool_configuration(
                    tool["tool_configuration"]
                ).data
                test = next(
                    (item for item in tests if item["tool"] == tool["id"]),
                    False,
                )
                update_project(
                    dc=dc,
                    engagement_id=engagement["id"],
                    tool_config=tool_configuration,
                    tool=tool,
                    test=test,
                    start_time=start_time,
                )

                # TODO: add exception handling
                # TODO: separate to different function
                # TODO: Use tool description (or special field in future)
                # to connect tool to the engagement


@main.command()
@click.option("--eng_id", "-e", help="Engagement ID", type=int)
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
        # TODO: separate to different functions
        # TODO: Use tool description (or special field in future)
        # to connect tool to the engagement


@main.command()
def update_all():
    dc = connector.Connector()
    start_time = datetime.now()
    for scanner_key, scanner in reports.SCANNERS.items():
        tool_configuration = dc.dd_v2.get_tool_configuration(scanner_key).data
        projects = reports.get_last_projects(tool_config=tool_configuration)
        for item in projects:
            print(item["name"])
            tools = dc.dd_v2.list_tool_products(
                tool_project_id=item[scanner["id"]],
                tool_configuration_id=tool_configuration["tool_type"],
            )

            if tools.data["results"]:
                tool = tools.data["results"][0]
                engagement = dc.dd_v2.get_engagement(tool["engagement"]).data
                tests = dc.dd_v2.list_tests(
                    test_type=scanner["test_type_id"], tool=tool["id"]
                ).data["results"]
                test = tests[0] if tests else False

            else:
                test = False
                engagement = create_engagement(
                    dc=dc, project=item, start_time=start_time
                )

                tool_base_url = tool_configuration['configuration_url'].replace("/app/api/v1", "")

                tool = dc.dd_v2.create_tool_product(
                    name="{}".format(engagement["name"]),
                    tool_configuration=scanner_key,
                    tool_project_id=item[scanner["id"]],
                    setting_url=scanner["project_url"].format(
                        tool_base_url,
                        item[scanner["id"]],
                    ),
                    engagement=engagement["id"],
                    product=engagement["product"],
                ).data

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


def create_engagement(dc, project, start_time, product=None):
    current_user = dc.dd_v2.list_users(username=dc.dd_v2.user).data["results"][
        0
    ]["id"]

    product_id = product if product else reports.UNSORTED_PRODUCT_ID
    # TODO check if name contains known prefix
    # TODO get info about git repository if exists
    # TODO set branch in the name
    engagement = dc.dd_v2.create_engagement(
        name=project["name"],
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
        test_updated = datetimestring = re.sub(
            r"([-+]\d{2}):(\d{2})(?:(\d{2}))?$", r"\1\2\3", test["updated"]
        )
        test_update_time = datetime.strptime(
            test_updated, "%Y-%m-%dT%H:%M:%S.%f%z"
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
            # return False

    if tool_config["tool_type"] == reports.APPSCREENER and test_update_time and tzinfo:
        new_scans = reports.get_new_scans(tool_config, tool, test_update_time, tzinfo)
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
                    test_type=reports.SCANNERS[tool_config["id"]]["test_type_id"],
                    environment=1,
                    target_start=start_time.strftime("%Y-%m-%d"),
                    target_end=start_time.strftime("%Y-%m-%d"),
                ).data

            limit = 20
            offset = 0
            if tool_config["tool_type"] == reports.APPSCREENER:
                amount = (
                    limit
                    if len(results["report"]["vulns"]) < limit
                    else len(results["report"]["vulns"])
                )
            else:
                amount = limit
            while offset + limit <= amount:
                if tool_config["tool_type"] == reports.APPSCREENER:
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

                res = dc.dd_v2.reupload_scan(
                    test_id=test["id"],
                    scan_type=results["scan_type"],
                    file=(results["file_name"], report),
                    active=True,
                    scan_date=start_time.strftime("%Y-%m-%d"),
                    tool=tool["id"],
                ).data
                print(test)
                offset += limit
    return success


@main.command()
def product_engagements_from_gitlab():
    """Load engagements.

    Load engagements of the product from Gitlab. Product - gitlab group, all
    projects in it will be engagements in defectdojo.
    """
    pass


# @click.option(
#   '--action',
#   default='add_product',
#   help='What you want to perform'
# )
# TODO: how to delete?
@main.command()
def engagement_delete_all():
    """Delete all products."""
    dc = connector.Connector()
    continue_delete = True
    while continue_delete:
        continue_delete = False
        engagements = dc.dd_v2.list_engagements(eng_type="CI/CD").data[
            "results"
        ]
        if len(engagements):
            continue_delete = True
            for engagement in engagements:
                dc.dd_v2.delete_engagement(engagement["id"])


@main.command()
def test_delete_all():
    """Delete all products."""
    dc = connector.Connector()
    continue_delete = True
    while continue_delete:
        continue_delete = False
        tests = dc.dd_v2.list_tests().data["results"]
        print(len(tests))
        if len(tests):
            continue_delete = True
            for test in tests:
                print(test["id"])
                dc.dd_v2.delete_test(test["id"])


@main.command()
@click.option("--test_id", "-t", help="Test ID", type=int)
def test_delete_findings(test_id):
    dc = connector.Connector()
    continue_delete = True
    while continue_delete:
        continue_delete = False
        findings = dc.dd_v2.list_findings(test=test_id).data["results"]
        if len(findings):
            continue_delete = True
            for finding in findings:
                dc.dd_v2.delete_finding(finding["id"])


if __name__ == "__main__":
    main()
