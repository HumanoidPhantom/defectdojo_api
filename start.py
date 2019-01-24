from defectdojo_api import defectdojo, connector
import click
from datetime import datetime, timedelta
import requests
import json
import time

NESSUS=1

@click.group()
def main():
    """CLI for Defect Dojo"""
    pass

@main.command()
def update_scans():
    """ Update all product scans

    """
    dojo_connector = connector.Connector()
    products = dojo_connector.dd_v2.list_products()

    for product in products.data["results"]:
        engagements = dojo_connector.dd_v2.list_engagements(product_id=product['id'],
                                                            eng_type="CI/CD")

        # TODO: Add field that would connect Engagemnt Test and Product Tool
        # TODO: lead_id - who is lead?
        start_time = datetime.now()
        for engagement in engagements.data["results"]:
            tools = dojo_connector.dd_v2.list_tool_products(product_id=product['id'],
                                                            description=engagement['name'])
            tests = dojo_connector.dd_v2.list_tests(engagement_id=engagement['id'])
            for tool in tools.data["results"]:
                tool_configuration = dojo_connector.dd_v2.get_tool_configuration(tool['tool_configuration'])

                if tool_configuration.data['tool_type'] == NESSUS:
                    # TODO: add exception handling
                    # TODO: separate to different function
                    # TODO: Use tool description (or special field in future) to connect tool to the engagement

                    request = requests.request(method='POST',
                                                url="{}/scans/{}/export".format(
                                                                        tool_configuration.data['configuration_url'],
                                                                        tool['tool_project_id']),
                                                headers={
                                                    "accept": "application/json",
                                                    "X-ApiKeys": tool_configuration.data['api_key']
                                                },
                                                verify=False,
                                                # proxies=proxies,
                                                data={"format":"nessus"})

                    file_info = json.loads(request.text)
                    loaded = False
                    counter = 0

                    while not loaded:

                        request = requests.request(method='GET',
                                                    url="{}/scans/{}/export/{}/status".format(
                                                                            tool_configuration.data['configuration_url'],
                                                                            tool['tool_project_id'],
                                                                            str(file_info['file'])),
                                                    headers={
                                                        "accept": "application/json",
                                                        "X-ApiKeys": tool_configuration.data['api_key']
                                                    },
                                                    verify=False)

                        result = json.loads(request.text)
                        if result['status'] == 'ready':
                            loaded = True
                            break

                        counter += 1
                        if counter > 10:
                            break

                        time.sleep(5)

                    if not counter > 10:
                        report = requests.request(method='GET',
                                            url="{}/tokens/{}/download".format(
                                                                    tool_configuration.data['configuration_url'],
                                                                    file_info['token']),
                                            headers={
                                                "accept": "application/json",
                                                "X-ApiKeys": tool_configuration.data['api_key']
                                            },
                                            verify=False)

                        test = next((item for item in tests.data["results"]
                                if "tool_" + str(tool["id"]) in item["tags"]), False)

                        if not test:
                            res = dojo_connector.dd_v2.upload_scan(engagement_id=engagement["id"],
                                                            scan_type="Nessus Scan",
                                                            active=True,
                                                            scan_date=start_time.strftime("%Y-%m-%d"),
                                                            minimum_severity="Info",
                                                            close_old_findings=True,
                                                            skip_duplicates=True,
                                                            file=('NessusScan.nessus', report.text),
                                                            tags=["tool_" + str(tool["id"])])
                        else:
                            res = dojo_connector.dd_v2.reupload_scan(test_id=test['id'],
                                                            scan_type="Nessus Scan",
                                                            file=('NessusScan.nessus', report.text),
                                                            active=True,
                                                            scan_date=start_time.strftime("%Y-%m-%d"))


@main.command()
def product_engagements_from_gitlab():
    """ Load engagements of the product from Gitlab. Product - gitlab group, all
    projects in it will be engagements in defectdojo

    """
    pass


@main.command()
# @click.option('--name', prompt="Product name", help="Product name")
# @click.option('--description', prompt="Description", help="Product description")
def product_add():
    """Add new product to Defect Dojo

    :param name: Product name
    :param description: Product description

    """

    dojo_connector = connector.Connector()
    res = dojo_connector.dd_v2.get_engagement()
    print(res.data_json(pretty=True))
    # product_type = 1 # TODO: How can we use it?
    # product = dojo_connector.dd_v2.create_product(name, description, product_type)

# @click.option('--action', default='add_product', help='What you want to perform')

# TODO: how to delete?
@main.command()
def engagement_delete_all():
    """Delete all products

    """
    dojo_connector = connector.Connector()

    engagements = dojo_connector.dd_v2.list_engagements(eng_type="CI/CD")

    for engagement in engagements.data["results"]:
        dojo_connector.dd_v2.delete_engagement(engagement["id"])

if __name__ == '__main__':
    main()
