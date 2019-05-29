from defectdojo_api import uploader
import click


@click.group()
def main():
    """CLI for Defect Dojo."""
    pass


@main.command()
@click.option(
    '--type', '-t',
    type=click.Choice(['all', 'engagement', 'nikto']),
    help="Update type:\n"
        "all (default) - updatel all products from "
        "Appscreener + Nessus scanners\n"
        "engagement - update specific engagement from "
        "Appscreener + Nessus scanners\n"
        "nikto - update from nikto scanner",
    default='all'
)
@click.option("--eng_id", "-e", help="Engagement ID", type=int)
@click.option("--file_path", "-f", help="Path to nikto scan results", type=str)
@click.option("--domain", "-d", help="Scanned domain name", type=str)
def update(type, eng_id, file_path, domain):
    if type == 'all':
        uploader.update_all()
    elif type == 'engagement':
        if not eng_id:
            print('eng_id should be specified')
            exit()
        uploader.update_engagement(eng_id)
    elif type == 'nikto':
        try:
            if not (file_path and domain):
                print("Domain name and file path for nikto " +
                    "scan results should be specified")
                exit()
            f = open(file_path, 'r')
            data = f.read()
            f.close()
            uploader.scan_nikto(data=data, domain=domain)
        except IOError as e:
            print('Cannot open file {}. Error: '.format(file_path), e)
    else:
        print("Wrong type")


@main.command()
def engagement_delete_all():
    """Delete all products."""
    uploader.engagement_delete_all()


@main.command()
def test_delete_all():
    """Delete all products."""
    uploader.test_delete_all()


@main.command()
@click.option("--test_id", "-t", help="Test ID", type=int)
def test_delete_findings(test_id):
    uploader.test_delete_findings(test_id)


if __name__ == "__main__":
    main()
