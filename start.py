from defectdojo_api import uploader
import click

DELETE_ENABLED = False
upload = None

@click.group()
@click.option("--config", "-c",
    help="Configuration file path. Default is 'config.yaml'",
    type=str,
    default="config.yaml"
)
@click.pass_context
def main(upload, config):
    """CLI for Defect Dojo."""
    upload.obj = uploader.Uploader(config=config)


@main.command()
@click.pass_obj
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
def update(upload, type, eng_id, file_path, domain):
    """Products update."""
    if type == 'all':
        upload.update_all()
    elif type == 'engagement':
        if not eng_id:
            print('eng_id should be specified')
            exit()
        upload.update_engagement(eng_id)
    elif type == 'nikto':
        try:
            if not (file_path and domain):
                print("Domain name and file path for nikto "
                    "scan results should be specified")
                exit()
            f = open(file_path, 'r')
            data = f.read()
            f.close()
            upload.update_nikto(data=data, domain=domain)
        except IOError as e:
            print('Cannot open file {}. Error: '.format(file_path), e)
    else:
        print("Wrong type")


@main.command()
@click.pass_obj
@click.option('--delete-all',
    help="Delete all engagements",
    is_flag=True)
@click.option(
    '--eng_id', '-e',
    help="Engagement ID, only if one engagement is being deleted",
)
def engagement_delete(upload, delete_all, eng_id):
    """Delete engagement."""
    check_delete()
    if delete_all:
        upload.engagement_delete_all()
    elif not eng_id:
        print('eng_id is required')
    else:
        upload.engagement_delete(eng_id)

@main.command()
@click.pass_obj
def test_delete_all(upload):
    """Delete all tests."""
    check_delete()
    upload.test_delete_all()


@main.command()
@click.pass_obj
@click.option("--test_id", "-t", help="Test ID", type=int)
def test_delete_findings(upload, test_id):
    """Delete findings in test."""
    check_delete()
    upload.test_delete_findings(test_id)


def check_delete():
    if not DELETE_ENABLED:
        print("Delete is currently disabled. Please, "
            "set 'DELETE_ENABLED' in defectdojo_api/uploader.py to True")
        exit()
    else:
        if not click.confirm('Are you sure you want to delete?'):
            exit()

if __name__ == "__main__":
    main()
