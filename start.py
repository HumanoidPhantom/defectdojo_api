from defectdojo_api import connector, reports
import click
from datetime import datetime, timedelta


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
            product_id=product['id'],
            eng_type="CI/CD"
        )
        # TODO: Add field that would connect Engagemnt Test and Product Tool
        # TODO: lead_id - who is lead?
        start_time = datetime.now()
        for engagement in engagements.data["results"]:
            dc.dd_v2.set_engagement(
                engagement['id'],
                target_end=(start_time+timedelta(weeks=1)).strftime("%Y-%m-%d")
            )
            tools = dc.dd_v2.list_tool_products(
                product_id=product['id'],
                description=engagement['name']
            )
            tests = dc.dd_v2.list_tests(
                engagement_id=engagement['id']
            )
            for tool in tools.data["results"]:
                tool_configuration = dc.dd_v2.get_tool_configuration(
                    tool['tool_configuration']
                )
                results = reports.get_results(
                    tool_configuration,
                    tool
                )
                if not results['report'] == "":
                    test = next(
                        (
                            item for item in tests.data["results"]
                            if "tool_" + str(tool['id'])
                            in item["tags"]
                        ),
                        False
                    )
                    if not test:
                        res = dc.dd_v2.upload_scan(
                            engagement_id=engagement["id"],
                            scan_type=results['scan_type'],
                            active=True,
                            scan_date=start_time.strftime("%Y-%m-%d"),
                            minimum_severity="Info",
                            close_old_findings=True,
                            skip_duplicates=True,
                            file=(results['file_name'], results['report']),
                            tags=["tool_" + str(tool['id'])]
                        )
                    else:
                        res = dc.dd_v2.reupload_scan(
                            test_id=test['id'],
                            scan_type=results['scan_type'],
                            file=(results['file_name'], results['report']),
                            active=True,
                            scan_date=start_time.strftime("%Y-%m-%d"),
                            tags=["tool_" + str(tool['id'])]
                        )
                    print(res)
                # TODO: add exception handling
                # TODO: separate to different function
                # TODO: Use tool description (or special field in future)
                # to connect tool to the engagement


@main.command()
def product_engagements_from_gitlab():
    """Load engagements.

    Load engagements of the product from Gitlab. Product - gitlab group, all
    projects in it will be engagements in defectdojo.
    """
    pass


@main.command()
# @click.option('--name', prompt="Product name", help="Product name")
# @click.option(
#   '--description',
#   prompt="Description",
#   help="Product description"
# )
def product_add():
    """Add new product to Defect Dojo.

    :param name: Product name
    :param description: Product description

    """
    dc = connector.Connector()
    res = dc.dd_v2.get_engagement()
    print(res.data_json(pretty=True))
    # product_type = 1 # TODO: How can we use it?
    # product = dc.dd_v2.create_product(name, description, product_type)


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

    engagements = dc.dd_v2.list_engagements(eng_type="CI/CD")

    for engagement in engagements.data["results"]:
        dc.dd_v2.delete_engagement(engagement["id"])


if __name__ == '__main__':
    main()
